"""绿地移交验收接口。"""

from flask import Blueprint, request

from ..schemas import (
    validate_acceptance,
    validate_completion,
    validate_defect,
    validate_defect_update,
    validate_handover,
    validate_revisit,
)
from ..schemas.filters import handover_filters
from ..services import HandoverAcceptanceService
from ..utils.pagination import paginate, parse_page_args
from ..utils.requests import json_body, query_flag
from ..utils.responses import created, ok

bp = Blueprint("handover_acceptances", __name__)


# ------------------------------------------------------------ 验收单
@bp.get("/handover-acceptances")
def list_handovers():
    filters = handover_filters(request.args)
    page, page_size = parse_page_args()
    query = HandoverAcceptanceService.list_acceptances(filters, request.args)
    data = paginate(
        query, page, page_size, serializer=HandoverAcceptanceService.serialize_row
    )
    data["summary"] = HandoverAcceptanceService.summary(filters)
    return ok(data)


@bp.get("/handover-acceptances/summary")
def handover_summary():
    return ok(HandoverAcceptanceService.summary(handover_filters(request.args)))


@bp.post("/handover-acceptances")
def create_handover():
    payload = validate_handover(json_body())
    handover = HandoverAcceptanceService.create(payload)
    return created(handover.to_dict(detail=True), message="移交验收单登记成功")


@bp.get("/handover-acceptances/<int:handover_id>")
def get_handover(handover_id):
    return ok(HandoverAcceptanceService.detail(handover_id))


@bp.put("/handover-acceptances/<int:handover_id>")
def update_handover(handover_id):
    payload = validate_handover(json_body(), require_items=False)
    handover = HandoverAcceptanceService.update(handover_id, payload)
    return ok(handover.to_dict(detail=True), message="移交验收单已更新")


@bp.delete("/handover-acceptances/<int:handover_id>")
def delete_handover(handover_id):
    result = HandoverAcceptanceService.delete(handover_id, force=query_flag("force"))
    return ok(result, message="移交验收单已删除")


# ------------------------------------------------------------ 验收/闭环
@bp.post("/handover-acceptances/<int:handover_id>/accept")
def accept_handover(handover_id):
    payload = validate_acceptance(json_body())
    handover = HandoverAcceptanceService.accept(handover_id, payload)
    return ok(handover.to_dict(detail=True), message="验收结果已提交")


@bp.post("/handover-acceptances/<int:handover_id>/complete")
def complete_handover(handover_id):
    payload = validate_completion(request.get_json(silent=True) or {})
    handover = HandoverAcceptanceService.complete(handover_id, payload)
    return ok(handover.to_dict(detail=True), message="缺陷已全部闭环，验收通过")


# ------------------------------------------------------------ 缺陷整改
@bp.post("/handover-acceptances/<int:handover_id>/defects")
def create_defect(handover_id):
    payload = validate_defect(json_body())
    defect = HandoverAcceptanceService.create_defect(handover_id, payload)
    return created(defect.to_dict(detail=True), message="缺陷已登记")


@bp.put("/handover-acceptances/<int:handover_id>/defects/<int:defect_id>")
def update_defect(handover_id, defect_id):
    payload = validate_defect_update(json_body())
    defect = HandoverAcceptanceService.update_defect(handover_id, defect_id, payload)
    return ok(defect.to_dict(detail=True), message="缺陷整改情况已更新")


@bp.delete("/handover-acceptances/<int:handover_id>/defects/<int:defect_id>")
def delete_defect(handover_id, defect_id):
    HandoverAcceptanceService.delete_defect(handover_id, defect_id)
    return ok(None, message="缺陷已删除")


# ------------------------------------------------------------ 质保回访
@bp.post("/handover-acceptances/<int:handover_id>/revisits")
def create_revisit(handover_id):
    payload = validate_revisit(json_body())
    revisit = HandoverAcceptanceService.create_revisit(handover_id, payload)
    return created(revisit.to_dict(detail=True), message="回访记录已登记")


@bp.put("/handover-acceptances/<int:handover_id>/revisits/<int:revisit_id>")
def update_revisit(handover_id, revisit_id):
    payload = validate_revisit(json_body())
    revisit = HandoverAcceptanceService.update_revisit(handover_id, revisit_id, payload)
    return ok(revisit.to_dict(detail=True), message="回访记录已更新")


@bp.delete("/handover-acceptances/<int:handover_id>/revisits/<int:revisit_id>")
def delete_revisit(handover_id, revisit_id):
    HandoverAcceptanceService.delete_revisit(handover_id, revisit_id)
    return ok(None, message="回访记录已删除")
