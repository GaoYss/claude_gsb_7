"""绿地移交验收接口与业务规则测试。"""

from datetime import date, timedelta

import pytest

from app.utils.dates import today

API = "/api/v1/handover-acceptances"


# ------------------------------------------------------------ 工厂辅助
def handover_payload(space_id, **overrides):
    payload = {
        "green_space_id": space_id,
        "transferor": "城建园林建设公司",
        "receiver": "区市政养护中心",
        "handover_date": "2026-09-01",
        "area_sqm": 3000,
        "warranty_months": 12,
        "plant_items": [
            {"plant_name": "香樟", "plant_category": "tree", "spec": "胸径 15cm", "quantity": 50},
            {"plant_name": "麦冬", "plant_category": "ground", "quantity": 800,
             "unit": "square_meter"},
        ],
    }
    payload.update(overrides)
    return payload


def accept_payload(handover, *, verdict="pass", **overrides):
    """根据已登记的验收单构造逐项核对全部符合的验收请求。"""

    items = [
        {
            "id": item.id,
            "checked_quantity": item.quantity,
            "growth_condition": "good",
            "check_result": "conform",
        }
        for item in handover.plant_items
    ]
    payload = {
        "inspector": "验收员王工",
        "acceptance_date": "2026-09-10",
        "verdict": verdict,
        "items": items,
        "defects": [],
    }
    if verdict == "pass":
        payload["checked_area_sqm"] = 2980
    payload.update(overrides)
    return payload


def create_handover(api, make_handover, make_space=None, **kwargs):
    """通过 service 建单（测试前置），返回 ORM 对象。"""

    return make_handover(**kwargs)


# ------------------------------------------------------------ 登记
def test_create_handover_generates_daily_code(api, make_space):
    space = make_space(established_date=date(2025, 1, 1))
    data = api.data(
        api.post(API, json=handover_payload(space.id)), expected_status=201
    )
    assert data["handover_no"].startswith(f"HA-{today().strftime('%Y%m%d')}-")
    assert data["status"] == "pending"
    assert data["warranty_months"] == 12
    assert len(data["plant_items"]) == 2

    second = api.data(
        api.post(API, json=handover_payload(space.id, transferor="另一施工单位")),
        expected_status=201,
    )
    assert second["handover_no"].endswith("-002")


def test_create_validates_fields_and_plant_rows(api, make_space):
    space = make_space(established_date=date(2025, 1, 1))
    response = api.post(
        API,
        json={
            "green_space_id": space.id,
            "handover_date": "2026-09-01",
            "plant_items": [{"plant_name": "", "plant_category": "bad", "quantity": 0}],
        },
    )
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert "transferor" in details
    assert "area_sqm" in details
    assert details["plant_items[0].plant_name"] == "苗木名称不能为空"
    assert "取值不合法" in details["plant_items[0].plant_category"]
    assert details["plant_items[0].quantity"] == "登记数量不能小于 0.01"


def test_create_requires_at_least_one_plant_row(api, make_space):
    space = make_space(established_date=date(2025, 1, 1))
    response = api.post(API, json=handover_payload(space.id, plant_items=[]))
    assert response.status_code == 422
    assert "plant_items" in response.get_json()["data"]


def test_create_validates_green_space(api, make_space):
    response = api.post(API, json=handover_payload(999999))
    assert response.status_code == 422
    assert response.get_json()["data"]["green_space_id"] == "所选绿地不存在"

    archived = make_space(status="archived")
    response = api.post(API, json=handover_payload(archived.id))
    assert response.status_code == 409

    space = make_space(established_date=date(2026, 1, 1))
    response = api.post(API, json=handover_payload(space.id, handover_date="2025-01-01"))
    assert response.status_code == 422
    assert "handover_date" in response.get_json()["data"]


# ------------------------------------------------------------ 验收
def test_accept_pass_sets_status_and_warranty(api, make_handover):
    handover = make_handover(handover_date=date(2026, 1, 1), warranty_months=1)
    data = api.data(
        api.post(
            f"{API}/{handover.id}/accept",
            json=accept_payload(handover, acceptance_date="2026-01-31"),
        )
    )
    assert data["status"] == "accepted"
    assert data["warranty_start_date"] == "2026-01-31"
    # 1 月 31 日 +1 个月，月末钳制为 2 月 28 日
    assert data["warranty_end_date"] == "2026-02-28"
    assert data["plant_items"][0]["checked_quantity"] == 50
    assert data["plant_items"][0]["growth_condition_label"] == "良好"


def test_accept_with_defects_turns_rectifying(api, make_handover):
    handover = make_handover()
    payload = accept_payload(
        handover,
        defects=[
            {"description": "色块缺株约 20 平方米", "location": "西北角",
             "severity": "general", "deadline": "2026-09-25", "responsible": "施工单位"}
        ],
    )
    data = api.data(api.post(f"{API}/{handover.id}/accept", json=payload))
    assert data["status"] == "rectifying"
    assert data["warranty_start_date"] is None
    assert len(data["defects"]) == 1
    assert data["defects"][0]["status"] == "pending"


def test_accept_pass_requires_full_check(api, make_handover):
    handover = make_handover()

    # 漏填第二行苗木的核对结论
    payload = accept_payload(handover)
    payload["items"][1].pop("check_result")
    response = api.post(f"{API}/{handover.id}/accept", json=payload)
    assert response.status_code == 422
    assert "items[1].check_result" in response.get_json()["data"]

    # 整行缺失
    payload = accept_payload(handover)
    payload["items"] = payload["items"][:1]
    response = api.post(f"{API}/{handover.id}/accept", json=payload)
    assert response.status_code == 422
    assert "items" in response.get_json()["data"]

    # 不属于本单的苗木行 id
    payload = accept_payload(handover)
    payload["items"][0]["id"] = 999999
    response = api.post(f"{API}/{handover.id}/accept", json=payload)
    assert response.status_code == 422
    assert "items[0].id" in response.get_json()["data"]

    # 通过但缺实测面积
    payload = accept_payload(handover)
    payload.pop("checked_area_sqm")
    response = api.post(f"{API}/{handover.id}/accept", json=payload)
    assert response.status_code == 422
    assert "checked_area_sqm" in response.get_json()["data"]


def test_accept_reject_cannot_carry_defects(api, make_handover):
    handover = make_handover()
    payload = accept_payload(
        handover,
        verdict="reject",
        defects=[{"description": "整体不合格", "deadline": "2026-09-25"}],
    )
    response = api.post(f"{API}/{handover.id}/accept", json=payload)
    assert response.status_code == 422
    assert "defects" in response.get_json()["data"]


def test_accept_only_allowed_before_rectifying(api, make_handover):
    handover = make_handover()
    api.data(api.post(
        f"{API}/{handover.id}/accept",
        json=accept_payload(handover, defects=[
            {"description": "x", "deadline": "2026-09-25"}]),
    ))
    response = api.post(
        f"{API}/{handover.id}/accept", json=accept_payload(handover)
    )
    assert response.status_code == 409


def test_accept_date_not_before_handover(api, make_handover):
    handover = make_handover(handover_date=date(2026, 9, 10))
    response = api.post(
        f"{API}/{handover.id}/accept",
        json=accept_payload(handover, acceptance_date="2026-09-01"),
    )
    assert response.status_code == 422
    assert "acceptance_date" in response.get_json()["data"]


# ------------------------------------------------------------ 缺陷整改
def _rectifying_handover(api, make_handover):
    handover = make_handover()
    data = api.data(api.post(
        f"{API}/{handover.id}/accept",
        json=accept_payload(handover, defects=[
            {"description": "缺陷一", "deadline": (today() + timedelta(days=5)).isoformat()},
            {"description": "缺陷二", "deadline": (today() - timedelta(days=1)).isoformat()},
        ]),
    ))
    return handover, data


def test_defect_rectify_close_lifecycle(api, make_handover):
    handover, data = _rectifying_handover(api, make_handover)
    defect = data["defects"][0]
    base = f"{API}/{handover.id}/defects/{defect['id']}"

    # 待整改不能直接闭环
    response = api.put(base, json={"status": "closed", "recheck_note": "复验合格"})
    assert response.status_code == 409

    # 标记已整改，服务端写整改时间
    data = api.data(api.put(base, json={"status": "rectified"}))
    assert data["status"] == "rectified"
    assert data["rectified_at"] is not None

    # 闭环必须填复验情况
    response = api.put(base, json={"status": "closed"})
    assert response.status_code == 422
    assert "recheck_note" in response.get_json()["data"]

    # 复验通过闭环
    data = api.data(api.put(base, json={"status": "closed", "recheck_note": "补植后合格"}))
    assert data["status"] == "closed"
    assert data["recheck_at"] is not None

    # 已闭环不能再改
    response = api.put(base, json={"responsible": "换单位"})
    assert response.status_code == 409


def test_defect_cross_handover_returns_404(api, make_handover):
    handover, data = _rectifying_handover(api, make_handover)
    other = make_handover(transferor="另一家单位")
    defect_id = data["defects"][0]["id"]
    response = api.put(
        f"{API}/{other.id}/defects/{defect_id}", json={"status": "rectified"}
    )
    assert response.status_code == 404


def test_add_and_delete_defect_during_rectifying(api, make_handover):
    handover, _ = _rectifying_handover(api, make_handover)

    created = api.data(
        api.post(f"{API}/{handover.id}/defects", json={
            "description": "复验新发现的排水问题", "deadline": "2026-10-01"}),
        expected_status=201,
    )
    assert created["severity"] == "general"

    # 待整改缺陷可删，进入整改流程后不可删
    api.data(api.put(
        f"{API}/{handover.id}/defects/{created['id']}", json={"status": "rectified"}))
    response = api.delete(f"{API}/{handover.id}/defects/{created['id']}")
    assert response.status_code == 409

    # 非整改中单据不能补登缺陷
    pending = make_handover()
    response = api.post(f"{API}/{pending.id}/defects",
                        json={"description": "x", "deadline": "2026-10-01"})
    assert response.status_code == 409


# ------------------------------------------------------------ 复验闭环
def test_complete_requires_all_defects_closed(api, make_handover):
    handover, data = _rectifying_handover(api, make_handover)

    response = api.post(f"{API}/{handover.id}/complete", json={})
    assert response.status_code == 409
    assert response.get_json()["data"]["open_defects"] == 2

    # 逐项闭环
    for defect in data["defects"]:
        api.data(api.put(
            f"{API}/{handover.id}/defects/{defect['id']}", json={"status": "rectified"}))
        api.data(api.put(
            f"{API}/{handover.id}/defects/{defect['id']}",
            json={"status": "closed", "recheck_note": "复验合格"}))

    result = api.data(api.post(
        f"{API}/{handover.id}/complete", json={"conclusion": "整改到位，同意接管"}))
    assert result["status"] == "accepted"
    # 质保起算沿用原验收日期（2026-09-10）
    assert result["warranty_start_date"] == "2026-09-10"
    assert result["warranty_end_date"] == "2027-09-10"

    # 已通过不能再次闭环
    assert api.post(f"{API}/{handover.id}/complete", json={}).status_code == 409


# ------------------------------------------------------------ 不通过与改单
def test_reject_then_revise_and_reaccept(api, make_handover):
    handover = make_handover(handover_date=date(2026, 9, 1))
    api.data(api.post(
        f"{API}/{handover.id}/accept",
        json=accept_payload(handover, verdict="reject",
                            acceptance_date="2026-09-05", conclusion="规格不符，退回")))

    detail = api.data(api.get(f"{API}/{handover.id}"))
    assert detail["status"] == "rejected"

    # 改单后回到待验收
    revised = handover_payload(
        handover.green_space_id,
        area_sqm=3100,
        plant_items=[
            {"plant_name": "香樟", "plant_category": "tree", "quantity": 52},
            {"plant_name": "麦冬", "plant_category": "ground", "quantity": 820,
             "unit": "square_meter"},
        ],
    )
    updated = api.data(api.put(f"{API}/{handover.id}", json=revised))
    assert updated["status"] == "pending"
    assert updated["acceptance_date"] is None
    assert len(updated["plant_items"]) == 2

    result = api.data(api.post(
        f"{API}/{handover.id}/accept",
        json=accept_payload(handover, acceptance_date="2026-09-20")))
    # 重新加载 items 以拿到新 id
    detail = api.data(api.get(f"{API}/{handover.id}"))
    assert detail["status"] == "accepted"
    assert detail["warranty_start_date"] == "2026-09-20"


def test_update_locked_after_acceptance(api, make_handover):
    handover, _ = _rectifying_handover(api, make_handover)
    response = api.put(f"{API}/{handover.id}",
                       json=handover_payload(handover.green_space_id, area_sqm=1))
    assert response.status_code == 409


# ------------------------------------------------------------ 删除保护
def test_delete_rules(api, make_handover):
    # 待验收可直接删
    pending = make_handover()
    assert api.delete(f"{API}/{pending.id}").status_code == 200
    assert api.get(f"{API}/{pending.id}").status_code == 404

    # 整改中带子数据需 force
    handover, _ = _rectifying_handover(api, make_handover)
    response = api.delete(f"{API}/{handover.id}")
    assert response.status_code == 409
    details = response.get_json()["data"]
    assert details["handover_defect"] >= 1
    assert api.delete(f"{API}/{handover.id}", force="true").status_code == 200

    # 验收通过恒禁止删除（force 也不行）
    accepted = make_handover()
    api.data(api.post(
        f"{API}/{accepted.id}/accept", json=accept_payload(accepted)))
    assert api.delete(f"{API}/{accepted.id}", force="true").status_code == 409


# ------------------------------------------------------------ 质保回访
def _accepted_handover(make_handover, **kwargs):
    handover = make_handover(**kwargs)
    from app.services import HandoverAcceptanceService

    payload = accept_payload(handover)
    payload["acceptance_date"] = date(2026, 9, 10)
    HandoverAcceptanceService.accept(handover.id, payload)
    return handover


def test_revisit_rules(api, make_handover):
    pending = make_handover()
    response = api.post(f"{API}/{pending.id}/revisits",
                        json={"visit_date": "2026-09-10", "result": "normal"})
    assert response.status_code == 409

    accepted = _accepted_handover(make_handover)

    # 回访日期不能早于验收日期
    response = api.post(f"{API}/{accepted.id}/revisits",
                        json={"visit_date": "2026-09-01", "result": "normal"})
    assert response.status_code == 422

    # 异常回访必须填问题
    response = api.post(f"{API}/{accepted.id}/revisits",
                        json={"visit_date": "2026-10-01", "result": "abnormal"})
    assert response.status_code == 422
    assert "issue" in response.get_json()["data"]

    # 正常回访
    revisit = api.data(
        api.post(f"{API}/{accepted.id}/revisits", json={
            "visit_date": "2026-10-01", "visitor": "李工",
            "survival_rate": 96.5, "result": "normal"}),
        expected_status=201,
    )
    assert revisit["survival_rate"] == 96.5

    # 异常回访（允许质保到期后登记）
    abnormal = api.data(
        api.post(f"{API}/{accepted.id}/revisits", json={
            "visit_date": "2028-01-01", "visitor": "李工", "result": "abnormal",
            "issue": "局部枯黄", "handling": "施肥浇水"}),
        expected_status=201,
    )
    assert abnormal["result_label"] == "异常"

    # 编辑与删除
    api.data(api.put(
        f"{API}/{accepted.id}/revisits/{revisit['id']}",
        json={"visit_date": "2026-10-02", "visitor": "李工", "result": "normal"}))
    assert api.delete(
        f"{API}/{accepted.id}/revisits/{revisit['id']}").status_code == 200

    # 越单访问 404
    other = _accepted_handover(make_handover, transferor="另一家单位")
    assert api.post(f"{API}/{other.id}/revisits", json={
        "visit_date": "2026-09-20", "result": "normal"}).status_code == 201
    assert api.delete(
        f"{API}/{other.id}/revisits/{abnormal['id']}").status_code == 404


# ------------------------------------------------------------ 列表与汇总
def test_list_filters_sorting_and_summary(api, make_handover):
    from app.services import HandoverAcceptanceService

    # 一张已通过、质保即将到期（约 10 天后到期）
    expiring = make_handover(handover_date=today() - timedelta(days=20), warranty_months=1)
    HandoverAcceptanceService.accept(expiring.id, {
        "inspector": "王工", "acceptance_date": today() - timedelta(days=20),
        "verdict": "pass", "checked_area_sqm": 2000,
        "items": [{"id": i.id, "checked_quantity": i.quantity,
                   "growth_condition": "good", "check_result": "conform"}
                  for i in expiring.plant_items],
        "defects": [],
    })
    # 一张整改中且有超期缺陷
    overdue = make_handover(handover_date=today() - timedelta(days=10), transferor="超期单位")
    HandoverAcceptanceService.accept(overdue.id, {
        "inspector": "王工", "acceptance_date": today() - timedelta(days=8),
        "verdict": "pass", "checked_area_sqm": 2900,
        "items": [{"id": i.id, "checked_quantity": i.quantity,
                   "growth_condition": "normal", "check_result": "conform"}
                  for i in overdue.plant_items],
        "defects": [{"description": "逾期缺陷", "deadline": today() - timedelta(days=2)}],
    })

    data = api.data(api.get(API, status="rectifying"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["progress"]["overdue_defect_count"] == 1

    data = api.data(api.get(API, overdue_defects="1"))
    assert data["meta"]["total"] == 1

    data = api.data(api.get(API, warranty_state="expiring"))
    assert data["meta"]["total"] == 1

    data = api.data(api.get(API, green_space_id=expiring.green_space_id))
    assert data["meta"]["total"] == 1

    data = api.data(api.get(API, keyword="超期单位"))
    assert data["meta"]["total"] == 1

    data = api.data(api.get(API, sort="handover_date", order="asc"))
    dates = [item["handover_date"] for item in data["items"]]
    assert dates == sorted(dates)

    summary = api.data(api.get(f"{API}/summary"))
    assert summary["by_status"]["accepted"] >= 1
    assert summary["by_status"]["rectifying"] >= 1
    assert summary["overdue_defect_count"] >= 1
    assert summary["warranty_expiring_count"] >= 1
    assert summary["total_area"] > 0


def test_detail_progress(api, make_handover):
    handover, data = _rectifying_handover(api, make_handover)
    detail = api.data(api.get(f"{API}/{handover.id}"))
    progress = detail["progress"]
    assert progress["item_count"] == 2
    assert progress["checked_count"] == 2
    assert progress["defect_count"] == 2
    assert progress["open_defect_count"] == 2
    assert "defect_status" in progress


# ------------------------------------------------------------ 绿地档案联动
def test_green_space_profile_includes_handovers(api, make_space, make_handover):
    from app.services import HandoverAcceptanceService

    space = make_space(established_date=date(2025, 1, 1))
    handover = make_handover(space=space)
    from app.services import HandoverAcceptanceService

    payload = accept_payload(handover)
    payload["acceptance_date"] = date(2026, 9, 10)
    HandoverAcceptanceService.accept(handover.id, payload)

    profile = api.data(api.get(f"/api/v1/green-spaces/{space.id}/profile"))
    stats = profile["statistics"]
    assert stats["handover_count"] == 1
    assert stats["accepted_count"] == 1
    assert stats["active_warranty_count"] == 1
    assert profile["recent_handovers"][0]["handover_no"] == handover.handover_no

def test_green_space_delete_protection_counts_handovers(api, make_space, make_handover):
    space = make_space(established_date=date(2025, 1, 1))
    make_handover(space=space)

    response = api.delete(f"/api/v1/green-spaces/{space.id}")
    assert response.status_code == 409
    assert "handover_acceptance" in response.get_json()["data"]

    api.data(api.delete(f"/api/v1/green-spaces/{space.id}", force="true"))
    assert api.get(f"/api/v1/green-spaces/{space.id}").status_code == 404


# ------------------------------------------------------------ 字典与演示数据
def test_meta_enums_include_handover_groups(api):
    enums = api.data(api.get("/api/v1/meta/enums"))["enums"]
    for key in ("handover_status", "handover_verdict", "growth_condition",
                "plant_check_result", "defect_severity", "defect_status", "revisit_result"):
        assert key in enums


def test_seeded_handover_aggregates_consistent(api, seeded):
    data = api.data(api.get(API, page_size=100))
    assert data["meta"]["total"] == seeded["handover_acceptance"]
    assert sum(
        data["summary"]["by_status"].values()
    ) == seeded["handover_acceptance"]
    assert data["summary"]["overdue_defect_count"] >= 1
    assert data["summary"]["warranty_expiring_count"] >= 1
