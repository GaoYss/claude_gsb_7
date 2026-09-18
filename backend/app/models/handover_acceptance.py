"""绿地移交验收模型：验收单主表 + 苗木清单 + 缺陷整改 + 质保回访。"""

from ..constants import (
    DEFECT_SEVERITY,
    DEFECT_STATUS,
    GROWTH_CONDITION,
    HANDOVER_STATUS,
    MEASURE_UNIT,
    PLANT_CATEGORY,
    PLANT_CHECK_RESULT,
    REVISIT_RESULT,
)
from ..extensions import db
from ..utils.dates import format_date, format_datetime, today
from ..utils.numbers import to_float
from .mixins import TimestampMixin, quantity_column


class HandoverAcceptance(TimestampMixin, db.Model):
    """新建/整治绿地移交养护的验收单，串联登记、核对、整改与质保回访。"""

    __tablename__ = "handover_acceptance"

    id = db.Column(db.Integer, primary_key=True)
    handover_no = db.Column(db.String(32), nullable=False, unique=True, index=True)
    green_space_id = db.Column(
        db.Integer, db.ForeignKey("green_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transferor = db.Column(db.String(128), nullable=False)
    receiver = db.Column(db.String(128))
    handover_date = db.Column(db.Date, nullable=False, index=True)
    area_sqm = db.Column(quantity_column(), nullable=False, default=0)
    checked_area_sqm = db.Column(quantity_column())
    warranty_months = db.Column(db.Integer, nullable=False, default=12)
    warranty_start_date = db.Column(db.Date)
    warranty_end_date = db.Column(db.Date, index=True)
    inspector = db.Column(db.String(64))
    acceptance_date = db.Column(db.Date, index=True)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    conclusion = db.Column(db.Text)
    remark = db.Column(db.Text)

    green_space = db.relationship("GreenSpace", back_populates="handovers", lazy="joined")
    plant_items = db.relationship(
        "HandoverPlantItem",
        back_populates="handover",
        cascade="all, delete-orphan",
        order_by="HandoverPlantItem.id",
    )
    defects = db.relationship(
        "HandoverDefect",
        back_populates="handover",
        cascade="all, delete-orphan",
        order_by="HandoverDefect.deadline.asc(), HandoverDefect.id.asc()",
    )
    revisits = db.relationship(
        "HandoverRevisit",
        back_populates="handover",
        cascade="all, delete-orphan",
        order_by="HandoverRevisit.visit_date.desc(), HandoverRevisit.id.desc()",
    )

    @property
    def warranty_active(self):
        """质保是否在保：已通过验收且质保到期日不早于今天。"""

        return self.status == "accepted" and self.warranty_end_date is not None \
            and self.warranty_end_date >= today()

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "handover_no": self.handover_no,
            "green_space_id": self.green_space_id,
            "green_space": self.green_space.to_brief() if self.green_space else None,
            "transferor": self.transferor,
            "receiver": self.receiver,
            "handover_date": format_date(self.handover_date),
            "area_sqm": to_float(self.area_sqm),
            "checked_area_sqm": to_float(self.checked_area_sqm),
            "warranty_months": self.warranty_months,
            "warranty_start_date": format_date(self.warranty_start_date),
            "warranty_end_date": format_date(self.warranty_end_date),
            "inspector": self.inspector,
            "acceptance_date": format_date(self.acceptance_date),
            "status": self.status,
            "status_label": HANDOVER_STATUS.label(self.status),
            "warranty_active": self.warranty_active,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
        if detail:
            data["conclusion"] = self.conclusion
            data["remark"] = self.remark
            data["plant_items"] = [item.to_dict() for item in self.plant_items]
            data["defects"] = [item.to_dict() for item in self.defects]
            data["revisits"] = [item.to_dict() for item in self.revisits]
        return data


class HandoverPlantItem(TimestampMixin, db.Model):
    """苗木清单：登记数量与验收时逐项核对的数量、长势、结论。"""

    __tablename__ = "handover_plant_item"

    id = db.Column(db.Integer, primary_key=True)
    handover_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plant_name = db.Column(db.String(96), nullable=False)
    plant_category = db.Column(db.String(32), nullable=False)
    spec = db.Column(db.String(64))
    quantity = db.Column(quantity_column(), nullable=False, default=0)
    checked_quantity = db.Column(quantity_column())
    unit = db.Column(db.String(16), nullable=False, default="plant")
    growth_condition = db.Column(db.String(16))
    check_result = db.Column(db.String(16))
    remark = db.Column(db.Text)

    handover = db.relationship("HandoverAcceptance", back_populates="plant_items", lazy="joined")

    @property
    def is_checked(self):
        return self.checked_quantity is not None or self.check_result is not None

    def to_dict(self, detail=False):
        return {
            "id": self.id,
            "handover_id": self.handover_id,
            "plant_name": self.plant_name,
            "plant_category": self.plant_category,
            "plant_category_label": PLANT_CATEGORY.label(self.plant_category),
            "spec": self.spec,
            "quantity": to_float(self.quantity),
            "checked_quantity": to_float(self.checked_quantity),
            "unit": self.unit,
            "unit_label": MEASURE_UNIT.label(self.unit),
            "growth_condition": self.growth_condition,
            "growth_condition_label": (
                GROWTH_CONDITION.label(self.growth_condition) if self.growth_condition else None
            ),
            "check_result": self.check_result,
            "check_result_label": (
                PLANT_CHECK_RESULT.label(self.check_result) if self.check_result else None
            ),
            "remark": self.remark,
        }


class HandoverDefect(TimestampMixin, db.Model):
    """缺陷整改清单：发现的缺陷、整改期限与复验闭环情况。"""

    __tablename__ = "handover_defect"

    id = db.Column(db.Integer, primary_key=True)
    handover_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(128))
    severity = db.Column(db.String(16), nullable=False, default="general", index=True)
    deadline = db.Column(db.Date, nullable=False, index=True)
    responsible = db.Column(db.String(96))
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    rectified_at = db.Column(db.DateTime)
    recheck_note = db.Column(db.Text)
    recheck_at = db.Column(db.DateTime)
    remark = db.Column(db.Text)

    handover = db.relationship("HandoverAcceptance", back_populates="defects", lazy="joined")

    @property
    def is_overdue(self):
        """未闭环且整改期限已过。"""

        return self.status != "closed" and self.deadline is not None and self.deadline < today()

    def to_dict(self, detail=False):
        return {
            "id": self.id,
            "handover_id": self.handover_id,
            "description": self.description,
            "location": self.location,
            "severity": self.severity,
            "severity_label": DEFECT_SEVERITY.label(self.severity),
            "deadline": format_date(self.deadline),
            "responsible": self.responsible,
            "status": self.status,
            "status_label": DEFECT_STATUS.label(self.status),
            "is_overdue": self.is_overdue,
            "rectified_at": format_datetime(self.rectified_at),
            "recheck_note": self.recheck_note,
            "recheck_at": format_datetime(self.recheck_at),
            "remark": self.remark,
        }


class HandoverRevisit(TimestampMixin, db.Model):
    """质保期回访记录，挂在同一份验收单下。"""

    __tablename__ = "handover_revisit"

    id = db.Column(db.Integer, primary_key=True)
    handover_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_date = db.Column(db.Date, nullable=False, index=True)
    visitor = db.Column(db.String(64))
    survival_rate = db.Column(quantity_column())
    issue = db.Column(db.Text)
    handling = db.Column(db.Text)
    result = db.Column(db.String(16), nullable=False, default="normal")
    next_visit_date = db.Column(db.Date)
    remark = db.Column(db.Text)

    handover = db.relationship("HandoverAcceptance", back_populates="revisits", lazy="joined")

    def to_dict(self, detail=False):
        return {
            "id": self.id,
            "handover_id": self.handover_id,
            "visit_date": format_date(self.visit_date),
            "visitor": self.visitor,
            "survival_rate": to_float(self.survival_rate, digits=1),
            "issue": self.issue,
            "handling": self.handling,
            "result": self.result,
            "result_label": REVISIT_RESULT.label(self.result),
            "next_visit_date": format_date(self.next_visit_date),
            "remark": self.remark,
        }
