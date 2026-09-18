"""绿地移交验收业务逻辑。

- 登记/改单：主表字段 + 苗木清单整单替换；
- 验收：逐项核对面积、数量与长势，开出缺陷整改清单；
- 整改：缺陷状态机（待整改 → 已整改待复验 → 已闭环），闭环后复验通过；
- 质保：验收通过后按验收日与质保月数派生质保起止，回访记录挂同一验收单。
"""

from datetime import timedelta

from sqlalchemy import exists, func, or_

from ..constants import ENUM_GROUPS
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import (
    GreenSpace,
    HandoverAcceptance,
    HandoverDefect,
    HandoverPlantItem,
    HandoverRevisit,
)
from ..models.mixins import utcnow
from ..utils.dates import add_months, format_date, today
from ..utils.numbers import to_float
from ..utils.sorting import parse_sort
from .base_service import BaseService
from .code_generator import daily_prefix

EDITABLE_STATUSES = ("pending", "rejected")
WARRANTY_EXPIRING_DAYS = 30


class HandoverAcceptanceService(BaseService):
    """移交验收单：登记、验收、整改闭环、质保回访的全流程规则。"""

    model = HandoverAcceptance
    label = "移交验收单"
    code_field = "handover_no"
    code_width = 3

    SORTABLE = {
        "handover_date": HandoverAcceptance.handover_date,
        "handover_no": HandoverAcceptance.handover_no,
        "acceptance_date": HandoverAcceptance.acceptance_date,
        "warranty_end_date": HandoverAcceptance.warranty_end_date,
        "created_at": HandoverAcceptance.created_at,
    }

    @classmethod
    def code_prefix(cls):
        return daily_prefix("HA")

    # ------------------------------------------------------------ 登记/改单
    @classmethod
    def prepare_instance(cls, instance, payload):
        green_space_id = payload.get("green_space_id", instance.green_space_id)
        space = db.session.get(GreenSpace, green_space_id) if green_space_id else None
        if space is None:
            raise ValidationError("登记失败", details={"green_space_id": "所选绿地不存在"})
        if space.status == "archived":
            raise ConflictError(f"绿地「{space.name}」已归档，不能再登记移交验收")

        handover_date = payload.get("handover_date", instance.handover_date)
        if handover_date and space.established_date and handover_date < space.established_date:
            raise ValidationError(
                "登记失败",
                details={
                    "handover_date": f"移交日期不能早于该绿地建成日期 {space.established_date}"
                },
            )
        # 验收/质保信息只能由验收动作写入，登记时一律复位
        instance.status = "pending"

    @classmethod
    def create(cls, data):
        data = dict(data)
        items = data.pop("plant_items", None) or []
        instance = super().create(data)
        cls._sync_items(instance, items)
        return instance

    @classmethod
    def update(cls, obj_id, data):
        instance = cls.get(obj_id)
        if instance.status not in EDITABLE_STATUSES:
            raise ConflictError("单据已进入验收流程，登记内容锁定，不能修改")

        data = dict(data)
        data.pop("green_space_id", None)  # 绿地归属创建后不可改
        items = data.pop("plant_items", None)
        was_rejected = instance.status == "rejected"

        instance = super().update(obj_id, data)
        # 不通过改单后重新回到待验收，清空上次验收结论
        if was_rejected:
            instance.status = "pending"
            instance.acceptance_date = None
            instance.checked_area_sqm = None
            instance.conclusion = None
        if items is not None:
            cls._sync_items(instance, items)
        else:
            db.session.commit()
        return instance

    @classmethod
    def _sync_items(cls, instance, items):
        """苗木清单整单替换（仅待验收/不通过状态调用，无核对数据需要保留）。"""

        instance.plant_items = [HandoverPlantItem(**row) for row in items]
        db.session.commit()

    # ------------------------------------------------------------ 验收
    @classmethod
    def accept(cls, obj_id, payload):
        """现场验收：更新逐项核对结果，按缺陷有无决定通过或转整改。"""

        handover = cls.get(obj_id)
        if handover.status not in EDITABLE_STATUSES:
            raise ConflictError("单据已进入验收流程，如需复验请走缺陷闭环")

        acceptance_date = payload.get("acceptance_date") or today()
        if acceptance_date < handover.handover_date:
            raise ValidationError(
                "验收失败", details={"acceptance_date": "验收日期不能早于移交日期"}
            )

        handover.acceptance_date = acceptance_date
        handover.inspector = payload["inspector"]
        handover.conclusion = payload.get("conclusion")

        if payload["verdict"] == "reject":
            if payload.get("defects"):
                raise ValidationError(
                    "验收失败",
                    details={"defects": "验收不通过时不开具整改清单，请整改后重新发起验收"},
                )
            handover.status = "rejected"
            db.session.commit()
            return handover

        # verdict = pass：实测面积与逐项核对为必填
        checked_area = payload.get("checked_area_sqm")
        errors = {}
        if checked_area is None:
            errors["checked_area_sqm"] = "验收通过时必须填写实测绿化面积"

        rows = payload.get("items", [])
        item_by_id = {item.id: item for item in handover.plant_items}
        checked_ids = set()
        for index, row in enumerate(rows):
            item = item_by_id.get(row["id"])
            if item is None:
                errors.setdefault(f"items[{index}].id", "苗木行不属于本验收单")
                continue
            checked_ids.add(row["id"])
            for field, label in (
                ("checked_quantity", "核对数量"),
                ("growth_condition", "长势"),
                ("check_result", "核对结论"),
            ):
                if row.get(field) is None:
                    errors.setdefault(f"items[{index}].{field}", f"{label}不能为空")
        if set(item_by_id) - checked_ids:
            errors.setdefault("items", "尚有苗木未完成逐项核对")
        if errors:
            raise ValidationError("验收失败", details=errors)

        handover.checked_area_sqm = checked_area
        for row in rows:
            item = item_by_id[row["id"]]
            item.checked_quantity = row["checked_quantity"]
            item.growth_condition = row["growth_condition"]
            item.check_result = row["check_result"]
            item.remark = row.get("remark")

        defects = payload.get("defects") or []
        for row in defects:
            db.session.add(
                HandoverDefect(
                    handover_id=handover.id,
                    description=row["description"],
                    location=row.get("location"),
                    severity=row.get("severity") or "general",
                    deadline=row["deadline"],
                    responsible=row.get("responsible"),
                )
            )

        if defects:
            handover.status = "rectifying"
        else:
            handover.status = "accepted"
            cls._apply_warranty(handover, acceptance_date)
        db.session.commit()
        return handover

    @classmethod
    def complete(cls, obj_id, payload=None):
        """整改复验闭环：所有缺陷闭环后转验收通过，并补算质保期。"""

        handover = cls.get(obj_id)
        if handover.status != "rectifying":
            raise ConflictError("仅整改中的验收单可以复验闭环")
        open_count = (
            db.session.query(func.count(HandoverDefect.id))
            .filter(HandoverDefect.handover_id == handover.id, HandoverDefect.status != "closed")
            .scalar()
            or 0
        )
        if open_count:
            raise ConflictError(
                f"仍有 {open_count} 项缺陷未完成整改复验，不能闭环",
                details={"open_defects": open_count},
            )

        handover.status = "accepted"
        if payload and payload.get("conclusion") is not None:
            handover.conclusion = payload["conclusion"]
        cls._apply_warranty(handover, handover.acceptance_date or today())
        db.session.commit()
        return handover

    @classmethod
    def _apply_warranty(cls, handover, start_date):
        """质保起算日只在首次通过验收时写入，到期日按月数派生。"""

        if handover.warranty_start_date is None:
            handover.warranty_start_date = start_date
            handover.warranty_end_date = add_months(start_date, handover.warranty_months or 12)

    # ------------------------------------------------------------ 缺陷整改
    @classmethod
    def create_defect(cls, obj_id, payload):
        handover = cls.get(obj_id)
        if handover.status != "rectifying":
            raise ConflictError("仅整改中的验收单可以补登缺陷")
        defect = HandoverDefect(
            handover_id=handover.id,
            description=payload["description"],
            location=payload.get("location"),
            severity=payload.get("severity") or "general",
            deadline=payload["deadline"],
            responsible=payload.get("responsible"),
            remark=payload.get("remark"),
        )
        db.session.add(defect)
        db.session.commit()
        return defect

    @classmethod
    def update_defect(cls, obj_id, defect_id, payload):
        handover = cls.get(obj_id)
        defect = cls._get_defect(handover, defect_id)
        if handover.status != "rectifying":
            raise ConflictError("仅整改中的验收单可以处理缺陷")
        if defect.status == "closed":
            raise ConflictError("该缺陷已闭环，不能再修改")

        new_status = payload.get("status", defect.status)
        transitions = {
            "pending": {"pending", "rectified"},
            "rectified": {"rectified", "closed"},
        }
        if new_status not in transitions.get(defect.status, set()):
            raise ConflictError("缺陷状态不能从「{0}」变更为「{1}」，请按整改→复验顺序推进".format(
                ENUM_GROUPS["defect_status"].label(defect.status),
                ENUM_GROUPS["defect_status"].label(new_status),
            ))

        if new_status == "closed":
            note = payload.get("recheck_note") if "recheck_note" in payload else defect.recheck_note
            if not note:
                raise ValidationError("闭环失败", details={"recheck_note": "复验通过闭环前必须填写复验情况"})
            defect.recheck_note = note
            defect.recheck_at = utcnow()
        elif new_status == "rectified" and defect.rectified_at is None:
            defect.rectified_at = utcnow()

        for field in ("description", "location", "severity", "deadline", "responsible", "remark"):
            if field in payload:
                setattr(defect, field, payload[field])
        if "recheck_note" in payload and new_status != "closed":
            defect.recheck_note = payload["recheck_note"]
        defect.status = new_status
        db.session.commit()
        return defect

    @classmethod
    def delete_defect(cls, obj_id, defect_id):
        handover = cls.get(obj_id)
        defect = cls._get_defect(handover, defect_id)
        if handover.status != "rectifying":
            raise ConflictError("仅整改中的验收单可以删除缺陷")
        if defect.status != "pending":
            raise ConflictError("已进入整改/复验流程的缺陷不能删除")
        db.session.delete(defect)
        db.session.commit()

    @classmethod
    def _get_defect(cls, handover, defect_id):
        defect = (
            db.session.query(HandoverDefect)
            .filter(HandoverDefect.id == defect_id, HandoverDefect.handover_id == handover.id)
            .first()
        )
        if defect is None:
            raise NotFoundError("缺陷不存在或不属于该验收单")
        return defect

    # ------------------------------------------------------------ 质保回访
    @classmethod
    def create_revisit(cls, obj_id, payload):
        handover = cls._require_accepted(obj_id)
        cls._validate_revisit(handover, payload)
        revisit = HandoverRevisit(handover_id=handover.id, **payload)
        db.session.add(revisit)
        db.session.commit()
        return revisit

    @classmethod
    def update_revisit(cls, obj_id, revisit_id, payload):
        handover = cls._require_accepted(obj_id)
        revisit = cls._get_revisit(handover, revisit_id)
        cls._validate_revisit(handover, payload)
        for field, value in payload.items():
            setattr(revisit, field, value)
        db.session.commit()
        return revisit

    @classmethod
    def delete_revisit(cls, obj_id, revisit_id):
        handover = cls._require_accepted(obj_id)
        revisit = cls._get_revisit(handover, revisit_id)
        db.session.delete(revisit)
        db.session.commit()

    @classmethod
    def _require_accepted(cls, obj_id):
        handover = cls.get(obj_id)
        if handover.status != "accepted":
            raise ConflictError("验收通过后才能登记质保回访")
        return handover

    @classmethod
    def _validate_revisit(cls, handover, payload):
        errors = {}
        visit_date = payload.get("visit_date")
        if visit_date and handover.acceptance_date and visit_date < handover.acceptance_date:
            errors["visit_date"] = "回访日期不能早于验收日期"
        if payload.get("result") == "abnormal" and not payload.get("issue"):
            errors["issue"] = "回访发现异常时必须填写问题描述"
        next_date = payload.get("next_visit_date")
        if visit_date and next_date and next_date < visit_date:
            errors["next_visit_date"] = "计划下次回访日期不能早于本次回访日期"
        if errors:
            raise ValidationError("回访登记失败", details=errors)

    @classmethod
    def _get_revisit(cls, handover, revisit_id):
        revisit = (
            db.session.query(HandoverRevisit)
            .filter(HandoverRevisit.id == revisit_id, HandoverRevisit.handover_id == handover.id)
            .first()
        )
        if revisit is None:
            raise NotFoundError("回访记录不存在或不属于该验收单")
        return revisit

    # ------------------------------------------------------------ 删除
    @classmethod
    def delete(cls, obj_id, force=False):
        handover = cls.get(obj_id)
        if handover.status == "accepted":
            raise ConflictError("验收已通过的移交验收单不允许删除")
        counts = {
            "handover_defect": len(handover.defects),
            "handover_revisit": len(handover.revisits),
        }
        if sum(counts.values()) and not force:
            raise ConflictError(
                "该验收单已登记缺陷 {handover_defect} 项、回访 {handover_revisit} 条，"
                "删除将一并清除，请确认后重试".format(**counts),
                details=counts,
            )
        db.session.delete(handover)
        db.session.commit()
        return {"deleted_defects": counts["handover_defect"], "deleted_revisits": counts["handover_revisit"]}

    # ------------------------------------------------------------ 查询
    @classmethod
    def _apply_filters(cls, query, filters):
        if filters.get("green_space_id"):
            query = query.filter(HandoverAcceptance.green_space_id == filters["green_space_id"])
        if filters.get("status"):
            query = query.filter(HandoverAcceptance.status == filters["status"])
        if filters.get("date_from"):
            query = query.filter(HandoverAcceptance.handover_date >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(HandoverAcceptance.handover_date <= filters["date_to"])
        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    HandoverAcceptance.handover_no.like(like),
                    HandoverAcceptance.transferor.like(like),
                    HandoverAcceptance.receiver.like(like),
                    HandoverAcceptance.inspector.like(like),
                )
            )
        state = filters.get("warranty_state")
        if state:
            query = query.filter(HandoverAcceptance.status == "accepted")
            if state == "active":
                query = query.filter(HandoverAcceptance.warranty_end_date >= today())
            elif state == "expired":
                query = query.filter(HandoverAcceptance.warranty_end_date < today())
            elif state == "expiring":
                query = query.filter(
                    HandoverAcceptance.warranty_end_date >= today(),
                    HandoverAcceptance.warranty_end_date <= today() + timedelta(
                        days=WARRANTY_EXPIRING_DAYS
                    ),
                )
        if filters.get("overdue_defects"):
            overdue_exists = (
                db.select(HandoverDefect.id)
                .where(
                    HandoverDefect.handover_id == HandoverAcceptance.id,
                    HandoverDefect.status != "closed",
                    HandoverDefect.deadline < today(),
                )
                .correlate(HandoverAcceptance)
                .exists()
            )
            query = query.filter(overdue_exists)
        return query

    @classmethod
    def list_acceptances(cls, filters, args):
        """列表带出苗木/缺陷/回访计数，避免 N+1。"""

        def count_subquery(*conditions):
            return (
                db.select(func.count())
                .select_from(HandoverDefect)
                .where(HandoverDefect.handover_id == HandoverAcceptance.id, *conditions)
                .correlate(HandoverAcceptance)
                .scalar_subquery()
            )

        item_count = (
            db.select(func.count(HandoverPlantItem.id))
            .where(HandoverPlantItem.handover_id == HandoverAcceptance.id)
            .correlate(HandoverAcceptance)
            .scalar_subquery()
        )
        defect_count = count_subquery()
        open_defect_count = count_subquery(HandoverDefect.status != "closed")
        overdue_defect_count = count_subquery(
            HandoverDefect.status != "closed", HandoverDefect.deadline < today()
        )
        revisit_count = (
            db.select(func.count(HandoverRevisit.id))
            .where(HandoverRevisit.handover_id == HandoverAcceptance.id)
            .correlate(HandoverAcceptance)
            .scalar_subquery()
        )
        query = db.session.query(
            HandoverAcceptance,
            item_count.label("item_count"),
            defect_count.label("defect_count"),
            open_defect_count.label("open_defect_count"),
            overdue_defect_count.label("overdue_defect_count"),
            revisit_count.label("revisit_count"),
        )
        query = cls._apply_filters(query, filters)
        return query.order_by(
            parse_sort(args, cls.SORTABLE, HandoverAcceptance.handover_date.desc())
        )

    @classmethod
    def serialize_row(cls, row):
        handover, item_count, defect_count, open_count, overdue_count, revisit_count = row
        data = handover.to_dict()
        data["progress"] = {
            "item_count": item_count or 0,
            "defect_count": defect_count or 0,
            "open_defect_count": open_count or 0,
            "overdue_defect_count": overdue_count or 0,
            "revisit_count": revisit_count or 0,
        }
        return data

    @classmethod
    def detail(cls, obj_id):
        handover = cls.get(obj_id)
        data = handover.to_dict(detail=True)
        items = handover.plant_items
        defects = handover.defects
        revisits = handover.revisits
        defect_status = {code: 0 for code in ENUM_GROUPS["defect_status"].values}
        for defect in defects:
            defect_status[defect.status] += 1
        days_remaining = (
            (handover.warranty_end_date - today()).days
            if handover.status == "accepted" and handover.warranty_end_date
            else None
        )
        data["progress"] = {
            "item_count": len(items),
            "checked_count": sum(1 for item in items if item.check_result is not None),
            "deficient_count": sum(1 for item in items if item.check_result == "deficient"),
            "defect_count": len(defects),
            "open_defect_count": sum(1 for defect in defects if defect.status != "closed"),
            "overdue_defect_count": sum(1 for defect in defects if defect.is_overdue),
            "defect_status": defect_status,
            "revisit_count": len(revisits),
            "last_visit_date": format_date(revisits[0].visit_date) if revisits else None,
            "warranty_days_remaining": days_remaining,
        }
        return data

    @classmethod
    def summary(cls, filters):
        """列表汇总：面积合计、状态分布、超期缺陷与质保即将到期提醒。"""

        total, area, checked_area = cls._apply_filters(
            db.session.query(
                func.count(HandoverAcceptance.id),
                func.coalesce(func.sum(HandoverAcceptance.area_sqm), 0),
                func.coalesce(func.sum(HandoverAcceptance.checked_area_sqm), 0),
            ),
            filters,
        ).one()

        status_rows = (
            cls._apply_filters(
                db.session.query(
                    HandoverAcceptance.status, func.count(HandoverAcceptance.id)
                ),
                filters,
            )
            .group_by(HandoverAcceptance.status)
            .all()
        )
        by_status = {code: 0 for code in ENUM_GROUPS["handover_status"].values}
        for status, count in status_rows:
            by_status[status] = count

        overdue_query = cls._apply_filters(
            db.session.query(func.count(HandoverDefect.id)).join(
                HandoverAcceptance, HandoverDefect.handover_id == HandoverAcceptance.id
            ),
            filters,
        ).filter(HandoverDefect.status != "closed", HandoverDefect.deadline < today())
        overdue_defect_count = overdue_query.scalar() or 0

        expiring_count = (
            cls._apply_filters(db.session.query(func.count(HandoverAcceptance.id)), filters)
            .filter(
                HandoverAcceptance.status == "accepted",
                HandoverAcceptance.warranty_end_date >= today(),
                HandoverAcceptance.warranty_end_date
                <= today() + timedelta(days=WARRANTY_EXPIRING_DAYS),
            )
            .scalar()
            or 0
        )

        return {
            "total_count": total or 0,
            "total_area": to_float(area) or 0,
            "total_checked_area": to_float(checked_area) or 0,
            "by_status": by_status,
            "overdue_defect_count": overdue_defect_count,
            "warranty_expiring_count": expiring_count,
        }
