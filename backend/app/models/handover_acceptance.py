"""绿地移交验收模型：验收单、苗木清单、整改清单与质保回访。"""

from ..constants import (
    ACCEPTANCE_STATUS,
    DEFECT_STATUS,
    FOLLOW_UP_STATUS,
    GROWTH_STATUS,
    ITEM_CHECK_RESULT,
    MEASURE_UNIT,
    PLANT_CATEGORY,
)
from ..extensions import db
from ..utils.dates import format_date, format_datetime, today
from ..utils.numbers import to_float
from .mixins import TimestampMixin, quantity_column

# 允许登记质保回访的验收单状态（验收通过、质保期内）
FOLLOW_UP_OPEN_STATUSES = ("passed",)


class HandoverAcceptance(TimestampMixin, db.Model):
    """移交验收单：新建绿地移交时的一次验收，串联苗木核对、整改与质保回访。"""

    __tablename__ = "handover_acceptance"

    id = db.Column(db.Integer, primary_key=True)
    acceptance_no = db.Column(db.String(32), nullable=False, unique=True, index=True)
    green_space_id = db.Column(
        db.Integer, db.ForeignKey("green_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    handover_party = db.Column(db.String(128), nullable=False)
    receiver = db.Column(db.String(128))
    area_sqm = db.Column(quantity_column(), nullable=False, default=0)
    warranty_months = db.Column(db.Integer, nullable=False, default=12)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    acceptance_date = db.Column(db.Date)
    measured_area_sqm = db.Column(quantity_column())
    warranty_end_date = db.Column(db.Date)
    inspector = db.Column(db.String(64))
    remark = db.Column(db.Text)

    green_space = db.relationship("GreenSpace", back_populates="acceptances", lazy="joined")
    plant_items = db.relationship(
        "AcceptancePlantItem",
        back_populates="acceptance",
        cascade="all, delete-orphan",
        order_by="AcceptancePlantItem.id.asc()",
    )
    defects = db.relationship(
        "AcceptanceDefect",
        back_populates="acceptance",
        cascade="all, delete-orphan",
        order_by="AcceptanceDefect.id.asc()",
    )
    follow_ups = db.relationship(
        "AcceptanceFollowUp",
        back_populates="acceptance",
        cascade="all, delete-orphan",
        order_by="AcceptanceFollowUp.visit_date.desc(), AcceptanceFollowUp.id.desc()",
    )

    @property
    def open_defect_count(self):
        return sum(1 for item in self.defects if item.status == "open")

    @property
    def open_follow_up_count(self):
        return sum(1 for item in self.follow_ups if item.status == "open")

    @property
    def is_warranty_expired(self):
        """质保截止日期早于今天即视为质保期满；未验收通过的验收单不适用。"""

        return self.warranty_end_date is not None and self.warranty_end_date < today()

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "acceptance_no": self.acceptance_no,
            "green_space_id": self.green_space_id,
            "green_space": self.green_space.to_brief() if self.green_space else None,
            "handover_party": self.handover_party,
            "receiver": self.receiver,
            "area_sqm": to_float(self.area_sqm),
            "warranty_months": self.warranty_months,
            "status": self.status,
            "status_label": ACCEPTANCE_STATUS.label(self.status),
            "acceptance_date": format_date(self.acceptance_date),
            "measured_area_sqm": to_float(self.measured_area_sqm),
            "warranty_end_date": format_date(self.warranty_end_date),
            "is_warranty_expired": self.is_warranty_expired,
            "inspector": self.inspector,
            "plant_count": len(self.plant_items),
            "defect_count": len(self.defects),
            "open_defect_count": self.open_defect_count,
            "follow_up_count": len(self.follow_ups),
            "open_follow_up_count": self.open_follow_up_count,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
        if detail:
            data["remark"] = self.remark
            data["plant_items"] = [item.to_dict() for item in self.plant_items]
            data["defects"] = [item.to_dict() for item in self.defects]
            data["follow_ups"] = [item.to_dict() for item in self.follow_ups]
        return data


class AcceptancePlantItem(TimestampMixin, db.Model):
    """苗木清单：登记时录入应移交数量，验收时逐项核对实核数量与长势。"""

    __tablename__ = "acceptance_plant_item"

    id = db.Column(db.Integer, primary_key=True)
    acceptance_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plant_name = db.Column(db.String(96), nullable=False)
    plant_category = db.Column(db.String(32), nullable=False, default="tree")
    spec = db.Column(db.String(64))
    quantity = db.Column(quantity_column(), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="plant")
    checked_quantity = db.Column(quantity_column())
    growth_status = db.Column(db.String(16))
    check_result = db.Column(db.String(16), nullable=False, default="unchecked")

    acceptance = db.relationship("HandoverAcceptance", back_populates="plant_items")

    def to_dict(self):
        return {
            "id": self.id,
            "acceptance_id": self.acceptance_id,
            "plant_name": self.plant_name,
            "plant_category": self.plant_category,
            "plant_category_label": PLANT_CATEGORY.label(self.plant_category),
            "spec": self.spec,
            "quantity": to_float(self.quantity),
            "unit": self.unit,
            "unit_label": MEASURE_UNIT.label(self.unit),
            "checked_quantity": to_float(self.checked_quantity),
            "growth_status": self.growth_status,
            "growth_status_label": (
                GROWTH_STATUS.label(self.growth_status) if self.growth_status else None
            ),
            "check_result": self.check_result,
            "check_result_label": ITEM_CHECK_RESULT.label(self.check_result),
        }


class AcceptanceDefect(TimestampMixin, db.Model):
    """整改清单：验收发现的缺陷，约定完成期限并跟踪整改结果。"""

    __tablename__ = "acceptance_defect"

    id = db.Column(db.Integer, primary_key=True)
    acceptance_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description = db.Column(db.String(255), nullable=False)
    requirement = db.Column(db.String(255))
    deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    finished_date = db.Column(db.Date)
    finished_note = db.Column(db.String(255))

    acceptance = db.relationship("HandoverAcceptance", back_populates="defects")

    @property
    def is_overdue(self):
        return self.status == "open" and self.deadline is not None and self.deadline < today()

    def to_dict(self):
        return {
            "id": self.id,
            "acceptance_id": self.acceptance_id,
            "description": self.description,
            "requirement": self.requirement,
            "deadline": format_date(self.deadline),
            "status": self.status,
            "status_label": DEFECT_STATUS.label(self.status),
            "is_overdue": self.is_overdue,
            "finished_date": format_date(self.finished_date),
            "finished_note": self.finished_note,
            "created_at": format_datetime(self.created_at),
        }


class AcceptanceFollowUp(TimestampMixin, db.Model):
    """质保回访：质保期内发现的问题与处理记录，挂在同一份验收单下。"""

    __tablename__ = "acceptance_follow_up"

    id = db.Column(db.Integer, primary_key=True)
    acceptance_id = db.Column(
        db.Integer,
        db.ForeignKey("handover_acceptance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_date = db.Column(db.Date, nullable=False)
    issue = db.Column(db.String(255), nullable=False)
    handling = db.Column(db.String(255))
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    visitor = db.Column(db.String(64))

    acceptance = db.relationship("HandoverAcceptance", back_populates="follow_ups")

    def to_dict(self):
        return {
            "id": self.id,
            "acceptance_id": self.acceptance_id,
            "visit_date": format_date(self.visit_date),
            "issue": self.issue,
            "handling": self.handling,
            "status": self.status,
            "status_label": FOLLOW_UP_STATUS.label(self.status),
            "visitor": self.visitor,
            "created_at": format_datetime(self.created_at),
        }
