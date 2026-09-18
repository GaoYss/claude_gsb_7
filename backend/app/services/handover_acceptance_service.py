"""绿地移交验收业务逻辑。

状态流转：

    待验收 ──验收登记──▶ 整改中 ──全部整改完成──▶ 验收通过 ──办结──▶ 已办结
       └──────验收无缺陷────────────▶ 验收通过（质保期自验收日期起算）

质保期内（验收通过）可登记回访；存在处理中的回访问题时不允许办结。
"""

from sqlalchemy import func, or_

from ..constants import ACCEPTANCE_STATUS
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import (
    AcceptanceDefect,
    AcceptanceFollowUp,
    AcceptancePlantItem,
    GreenSpace,
    HandoverAcceptance,
)
from ..utils.dates import add_months
from ..utils.sorting import parse_sort
from .base_service import BaseService
from .code_generator import daily_prefix


class HandoverAcceptanceService(BaseService):
    """移交验收单：登记、验收核对、整改跟踪与质保回访。"""

    model = HandoverAcceptance
    label = "移交验收单"
    code_field = "acceptance_no"
    code_width = 3

    SORTABLE = {
        "acceptance_date": HandoverAcceptance.acceptance_date,
        "area_sqm": HandoverAcceptance.area_sqm,
        "warranty_end_date": HandoverAcceptance.warranty_end_date,
        "created_at": HandoverAcceptance.created_at,
    }

    @classmethod
    def code_prefix(cls):
        return daily_prefix("HA")

    # ------------------------------------------------------------ 校验与派生
    @classmethod
    def prepare_instance(cls, instance, payload):
        green_space_id = payload.get("green_space_id", instance.green_space_id)
        space = db.session.get(GreenSpace, green_space_id) if green_space_id else None
        if space is None:
            raise ValidationError("登记失败", details={"green_space_id": "所选绿地不存在"})

    @classmethod
    def prepare_update(cls, instance, payload):
        if instance.status == "closed":
            raise ConflictError("验收单已办结，不允许再修改")
        cls.prepare_instance(instance, payload)

    @classmethod
    def apply_derived(cls, instance):
        """质保截止日期 = 验收日期 + 质保月数；验收通过后随质保期调整自动重算。"""

        if instance.acceptance_date and instance.status in ("passed", "closed"):
            instance.warranty_end_date = add_months(
                instance.acceptance_date, instance.warranty_months or 0
            )

    # ------------------------------------------------------------ 创建与更新（含苗木清单）
    @classmethod
    def create(cls, data):
        data = dict(data)
        plants = data.pop("plants", None)
        instance = super().create(data)
        if plants:
            cls._sync_plants(instance, plants)
            db.session.commit()
        return instance

    @classmethod
    def update(cls, obj_id, data):
        data = dict(data)
        plants = data.pop("plants", None)
        if plants is not None:
            instance = cls.get(obj_id)
            if instance.status != "pending":
                raise ValidationError(
                    "苗木清单已在验收时核对，仅待验收状态可调整",
                    details={"plants": "当前状态不允许修改苗木清单"},
                )
        instance = super().update(obj_id, data)
        if plants is not None:
            cls._sync_plants(instance, plants)
            db.session.commit()
        return instance

    @staticmethod
    def _sync_plants(instance, plants):
        """整体替换苗木清单（仅限待验收阶段调用）。"""

        db.session.query(AcceptancePlantItem).filter_by(acceptance_id=instance.id).delete()
        for row in plants:
            db.session.add(AcceptancePlantItem(acceptance_id=instance.id, **row))
        db.session.flush()

    # ------------------------------------------------------------ 验收登记
    @classmethod
    def accept(cls, obj_id, data):
        """验收登记：写入逐项核对结果与缺陷清单，并按缺陷情况推进状态。"""

        instance = cls.get(obj_id)
        if instance.status not in ("pending", "rectifying"):
            raise ConflictError(f"当前状态为「{ACCEPTANCE_STATUS.label(instance.status)}」，不允许验收登记")

        space = instance.green_space
        acceptance_date = data["acceptance_date"]
        if space and space.established_date and acceptance_date < space.established_date:
            raise ValidationError(
                "验收失败",
                details={
                    "acceptance_date": f"验收日期不能早于该绿地建成日期 {space.established_date}"
                },
            )

        instance.acceptance_date = acceptance_date
        instance.measured_area_sqm = data.get("measured_area_sqm")
        if data.get("inspector"):
            instance.inspector = data["inspector"]

        items_by_id = {item.id: item for item in instance.plant_items}
        for check in data.get("checks") or []:
            item = items_by_id.get(check["plant_item_id"])
            if item is None:
                raise ValidationError(
                    "验收失败",
                    details={"checks": f"苗木清单行 {check['plant_item_id']} 不属于本验收单"},
                )
            item.checked_quantity = check.get("checked_quantity")
            item.growth_status = check.get("growth_status")
            item.check_result = check["check_result"]

        for row in data.get("defects") or []:
            db.session.add(AcceptanceDefect(acceptance_id=instance.id, **row))

        db.session.flush()
        cls._refresh_status(instance)
        db.session.commit()
        return instance

    @staticmethod
    def _refresh_status(instance):
        """按验收日期与未整改缺陷重算验收单状态。"""

        if instance.acceptance_date is None:
            return
        if any(defect.status == "open" for defect in instance.defects):
            instance.status = "rectifying"
        else:
            instance.status = "passed"
            instance.warranty_end_date = add_months(
                instance.acceptance_date, instance.warranty_months or 0
            )

    # ------------------------------------------------------------ 整改清单
    @classmethod
    def add_defect(cls, obj_id, data):
        """补录缺陷：验收后发现的遗漏问题可追加，追加后验收单回到整改中。"""

        instance = cls.get(obj_id)
        if instance.status == "closed":
            raise ConflictError("验收单已办结，不允许再登记缺陷")
        defect = AcceptanceDefect(acceptance_id=instance.id, **data)
        db.session.add(defect)
        db.session.flush()
        cls._refresh_status(instance)
        db.session.commit()
        return defect

    @classmethod
    def complete_defect(cls, obj_id, defect_id, data):
        """标记缺陷整改完成；全部完成时验收单自动转为验收通过。"""

        instance = cls.get(obj_id)
        defect = cls._get_defect(instance, defect_id)
        if defect.status == "done":
            raise ConflictError("该缺陷已标记整改完成，请勿重复操作")
        defect.status = "done"
        defect.finished_date = data["finished_date"]
        defect.finished_note = data.get("finished_note")
        db.session.flush()
        cls._refresh_status(instance)
        db.session.commit()
        return instance

    @classmethod
    def delete_defect(cls, obj_id, defect_id):
        """删除缺陷：仅限待整改的缺陷，已整改记录作为验收履历保留。"""

        instance = cls.get(obj_id)
        defect = cls._get_defect(instance, defect_id)
        if defect.status == "done":
            raise ConflictError("该缺陷已整改完成，不允许删除")
        db.session.delete(defect)
        db.session.flush()
        cls._refresh_status(instance)
        db.session.commit()
        return instance

    @staticmethod
    def _get_defect(instance, defect_id):
        defect = db.session.get(AcceptanceDefect, defect_id)
        if defect is None or defect.acceptance_id != instance.id:
            raise NotFoundError("整改缺陷不存在或不属于该验收单")
        return defect

    # ------------------------------------------------------------ 质保回访
    @classmethod
    def add_follow_up(cls, obj_id, data):
        """登记质保回访：仅验收通过（质保期内）的验收单可登记。"""

        instance = cls.get(obj_id)
        if instance.status != "passed":
            raise ConflictError("验收通过（质保期内）的验收单才能登记回访记录")
        follow_up = AcceptanceFollowUp(acceptance_id=instance.id, **data)
        db.session.add(follow_up)
        db.session.commit()
        return follow_up

    @classmethod
    def update_follow_up(cls, obj_id, follow_up_id, data):
        instance = cls.get(obj_id)
        if instance.status == "closed":
            raise ConflictError("验收单已办结，回访记录不允许再修改")
        follow_up = db.session.get(AcceptanceFollowUp, follow_up_id)
        if follow_up is None or follow_up.acceptance_id != instance.id:
            raise NotFoundError("回访记录不存在或不属于该验收单")
        for field, value in data.items():
            setattr(follow_up, field, value)
        db.session.commit()
        return follow_up

    # ------------------------------------------------------------ 办结
    @classmethod
    def close(cls, obj_id):
        """办结：质保责任结束；存在处理中的回访问题时不允许办结。"""

        instance = cls.get(obj_id)
        if instance.status == "closed":
            raise ConflictError("验收单已办结，请勿重复操作")
        if instance.status != "passed":
            raise ConflictError("仅验收通过的验收单可以办结")
        if instance.open_follow_up_count:
            raise ConflictError(
                f"尚有 {instance.open_follow_up_count} 条回访问题处理中，处理完成后才能办结"
            )
        instance.status = "closed"
        db.session.commit()
        return instance

    # ------------------------------------------------------------ 删除
    @classmethod
    def delete(cls, obj_id, force=False):
        instance = cls.get(obj_id)
        counts = {
            "plant_item": len(instance.plant_items),
            "defect": len(instance.defects),
            "follow_up": len(instance.follow_ups),
        }
        if sum(counts.values()) and not force:
            raise ConflictError(
                "该验收单已存在苗木清单 {plant_item} 项、整改缺陷 {defect} 条、"
                "回访记录 {follow_up} 条，删除将一并清除，请确认后重试".format(**counts),
                details=counts,
            )
        db.session.delete(instance)
        db.session.commit()
        return counts

    # ------------------------------------------------------------ 查询
    @classmethod
    def _apply_filters(cls, query, filters):
        if filters.get("green_space_id"):
            query = query.filter(HandoverAcceptance.green_space_id == filters["green_space_id"])
        if filters.get("status"):
            query = query.filter(HandoverAcceptance.status == filters["status"])
        if filters.get("date_from"):
            query = query.filter(HandoverAcceptance.acceptance_date >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(HandoverAcceptance.acceptance_date <= filters["date_to"])
        if filters.get("defect_open"):
            query = query.filter(
                HandoverAcceptance.defects.any(AcceptanceDefect.status == "open")
            )
        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    HandoverAcceptance.acceptance_no.like(like),
                    HandoverAcceptance.handover_party.like(like),
                    HandoverAcceptance.receiver.like(like),
                    HandoverAcceptance.inspector.like(like),
                )
            )
        return query

    @classmethod
    def list_acceptances(cls, filters, args):
        query = cls._apply_filters(db.session.query(HandoverAcceptance), filters)
        return query.order_by(
            parse_sort(args, cls.SORTABLE, HandoverAcceptance.created_at.desc())
        )

    @classmethod
    def detail(cls, obj_id):
        return cls.get(obj_id).to_dict(detail=True)

    @classmethod
    def summary(cls, filters):
        """验收汇总：状态分布、待整改缺陷与处理中回访数量。"""

        status_rows = (
            cls._apply_filters(
                db.session.query(HandoverAcceptance.status, func.count(HandoverAcceptance.id)),
                filters,
            )
            .group_by(HandoverAcceptance.status)
            .all()
        )
        by_status = {code: 0 for code in ACCEPTANCE_STATUS.values}
        for status, count in status_rows:
            by_status[status] = count

        defect_count = (
            cls._apply_filters(
                db.session.query(func.count(AcceptanceDefect.id)).select_from(HandoverAcceptance)
                .join(AcceptanceDefect, AcceptanceDefect.acceptance_id == HandoverAcceptance.id),
                {k: v for k, v in filters.items() if k != "defect_open"},
            )
            .filter(AcceptanceDefect.status == "open")
            .scalar()
        ) or 0
        follow_up_count = (
            cls._apply_filters(
                db.session.query(func.count(AcceptanceFollowUp.id)).select_from(HandoverAcceptance)
                .join(AcceptanceFollowUp, AcceptanceFollowUp.acceptance_id == HandoverAcceptance.id),
                {k: v for k, v in filters.items() if k != "defect_open"},
            )
            .filter(AcceptanceFollowUp.status == "open")
            .scalar()
        ) or 0

        return {
            "total_count": sum(by_status.values()),
            "by_status": by_status,
            "open_defect_count": defect_count,
            "open_follow_up_count": follow_up_count,
        }
