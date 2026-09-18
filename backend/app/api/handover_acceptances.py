"""绿地移交验收接口。"""

from flask import Blueprint, request

from ..schemas import (
    validate_acceptance_accept,
    validate_acceptance_defect,
    validate_acceptance_follow_up,
    validate_defect_complete,
    validate_handover_acceptance,
)
from ..schemas.filters import acceptance_filters
from ..services import HandoverAcceptanceService
from ..utils.pagination import paginate, parse_page_args
from ..utils.requests import json_body
from ..utils.responses import created, ok

bp = Blueprint("handover_acceptances", __name__)


@bp.get("/handover-acceptances")
def list_acceptances():
    filters = acceptance_filters(request.args)
    page, page_size = parse_page_args()
    query = HandoverAcceptanceService.list_acceptances(filters, request.args)
    data = paginate(query, page, page_size)
    data["summary"] = HandoverAcceptanceService.summary(filters)
    return ok(data)


@bp.post("/handover-acceptances")
def create_acceptance():
    payload = validate_handover_acceptance(json_body())
    acceptance = HandoverAcceptanceService.create(payload)
    return created(acceptance.to_dict(detail=True), message="移交验收单登记成功")


@bp.get("/handover-acceptances/<int:acceptance_id>")
def get_acceptance(acceptance_id):
    return ok(HandoverAcceptanceService.detail(acceptance_id))


@bp.put("/handover-acceptances/<int:acceptance_id>")
def update_acceptance(acceptance_id):
    payload = validate_handover_acceptance(json_body())
    acceptance = HandoverAcceptanceService.update(acceptance_id, payload)
    return ok(acceptance.to_dict(detail=True), message="移交验收单已更新")


@bp.delete("/handover-acceptances/<int:acceptance_id>")
def delete_acceptance(acceptance_id):
    force = str(request.args.get("force", "")).lower() in {"1", "true", "yes"}
    HandoverAcceptanceService.delete(acceptance_id, force=force)
    return ok(None, message="移交验收单已删除")


@bp.post("/handover-acceptances/<int:acceptance_id>/accept")
def accept(acceptance_id):
    payload = validate_acceptance_accept(json_body())
    acceptance = HandoverAcceptanceService.accept(acceptance_id, payload)
    return ok(acceptance.to_dict(detail=True), message="验收登记完成")


@bp.post("/handover-acceptances/<int:acceptance_id>/defects")
def add_defect(acceptance_id):
    payload = validate_acceptance_defect(json_body())
    HandoverAcceptanceService.add_defect(acceptance_id, payload)
    return created(HandoverAcceptanceService.detail(acceptance_id), message="缺陷已登记")


@bp.patch("/handover-acceptances/<int:acceptance_id>/defects/<int:defect_id>/complete")
def complete_defect(acceptance_id, defect_id):
    payload = validate_defect_complete(json_body())
    acceptance = HandoverAcceptanceService.complete_defect(acceptance_id, defect_id, payload)
    return ok(acceptance.to_dict(detail=True), message="缺陷已标记整改完成")


@bp.delete("/handover-acceptances/<int:acceptance_id>/defects/<int:defect_id>")
def delete_defect(acceptance_id, defect_id):
    acceptance = HandoverAcceptanceService.delete_defect(acceptance_id, defect_id)
    return ok(acceptance.to_dict(detail=True), message="缺陷已删除")


@bp.post("/handover-acceptances/<int:acceptance_id>/follow-ups")
def add_follow_up(acceptance_id):
    payload = validate_acceptance_follow_up(json_body())
    HandoverAcceptanceService.add_follow_up(acceptance_id, payload)
    return created(HandoverAcceptanceService.detail(acceptance_id), message="回访记录已登记")


@bp.put("/handover-acceptances/<int:acceptance_id>/follow-ups/<int:follow_up_id>")
def update_follow_up(acceptance_id, follow_up_id):
    payload = validate_acceptance_follow_up(json_body())
    HandoverAcceptanceService.update_follow_up(acceptance_id, follow_up_id, payload)
    return ok(HandoverAcceptanceService.detail(acceptance_id), message="回访记录已更新")


@bp.post("/handover-acceptances/<int:acceptance_id>/close")
def close(acceptance_id):
    acceptance = HandoverAcceptanceService.close(acceptance_id)
    return ok(acceptance.to_dict(detail=True), message="验收单已办结")
