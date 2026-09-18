"""绿地移交验收接口与业务规则测试。"""

from datetime import date


def acceptance_payload(space_id, **overrides):
    payload = {
        "green_space_id": space_id,
        "handover_party": "市政园林工程公司",
        "receiver": "区绿化养护管理所",
        "area_sqm": 3200,
        "warranty_months": 24,
        "inspector": "钱工",
        "plants": [
            {"plant_name": "银杏", "plant_category": "tree", "spec": "胸径 14-16cm",
             "quantity": 60, "unit": "plant"},
            {"plant_name": "金森女贞", "plant_category": "shrub", "spec": "H40cm",
             "quantity": 900, "unit": "square_meter"},
        ],
    }
    payload.update(overrides)
    return payload


def accept_payload(acceptance, **overrides):
    checks = [
        {"plant_item_id": item["id"], "checked_quantity": item["quantity"],
         "growth_status": "good", "check_result": "qualified"}
        for item in acceptance["plant_items"]
    ]
    payload = {
        "acceptance_date": "2026-03-20",
        "measured_area_sqm": 3180,
        "inspector": "钱工",
        "checks": checks,
    }
    payload.update(overrides)
    return payload


def create_acceptance(api, space_id, **overrides):
    return api.data(
        api.post("/api/v1/handover-acceptances", acceptance_payload(space_id, **overrides)), 201
    )


def accept(api, acceptance, **overrides):
    return api.data(
        api.post(f"/api/v1/handover-acceptances/{acceptance['id']}/accept",
                 accept_payload(acceptance, **overrides))
    )


# ---------------------------------------------------------------- 登记

def test_create_acceptance_with_plant_list(api, make_space):
    space = make_space()
    data = create_acceptance(api, space.id)
    assert data["acceptance_no"].startswith("HA-")
    assert data["status"] == "pending"
    assert data["status_label"] == "待验收"
    assert data["handover_party"] == "市政园林工程公司"
    assert data["area_sqm"] == 3200.0
    assert data["warranty_months"] == 24
    assert data["warranty_end_date"] is None
    assert len(data["plant_items"]) == 2
    first = data["plant_items"][0]
    assert first["plant_name"] == "银杏"
    assert first["check_result"] == "unchecked"
    assert first["unit_label"] == "株"


def test_acceptance_no_is_unique_and_incremental(api, make_space):
    space = make_space()
    first = create_acceptance(api, space.id)
    second = create_acceptance(api, space.id)
    assert first["acceptance_no"] != second["acceptance_no"]


def test_required_fields_and_ranges_are_validated(api, make_space):
    space = make_space()
    response = api.post("/api/v1/handover-acceptances", acceptance_payload(
        space.id, handover_party="", area_sqm=0, warranty_months=0))
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert "handover_party" in details
    assert "area_sqm" in details
    assert "warranty_months" in details


def test_plant_row_errors_carry_row_index(api, make_space):
    space = make_space()
    payload = acceptance_payload(space.id, plants=[
        {"plant_name": "", "quantity": 0, "unit": "plant"},
        {"plant_name": "香樟", "quantity": 10, "unit": "plant"},
    ])
    response = api.post("/api/v1/handover-acceptances", payload)
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert "plants.0.plant_name" in details
    assert "plants.0.quantity" in details
    assert not any(key.startswith("plants.1") for key in details)


def test_green_space_must_exist(api):
    response = api.post("/api/v1/handover-acceptances", acceptance_payload(9999))
    assert response.status_code == 422
    assert "green_space_id" in response.get_json()["data"]


# ---------------------------------------------------------------- 验收登记

def test_accept_without_defects_passes_and_computes_warranty(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    data = accept(api, acceptance)
    assert data["status"] == "passed"
    assert data["acceptance_date"] == "2026-03-20"
    assert data["measured_area_sqm"] == 3180.0
    assert data["warranty_end_date"] == "2028-03-20"  # 验收日期 + 24 个月
    assert all(item["check_result"] == "qualified" for item in data["plant_items"])
    assert all(item["growth_status"] == "good" for item in data["plant_items"])


def test_accept_with_defects_enters_rectifying(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    data = accept(api, acceptance, defects=[
        {"description": "3 株银杏死亡", "requirement": "更换同规格苗木", "deadline": "2026-04-10"},
    ])
    assert data["status"] == "rectifying"
    assert data["open_defect_count"] == 1
    defect = data["defects"][0]
    assert defect["status"] == "open"
    assert defect["deadline"] == "2026-04-10"


def test_accept_rejects_unknown_plant_item(api, make_space, make_acceptance):
    acceptance = create_acceptance(api, make_space().id)
    other = make_acceptance()
    foreign_item_id = other.plant_items[0].id
    response = api.post(
        f"/api/v1/handover-acceptances/{acceptance['id']}/accept",
        accept_payload(acceptance, checks=[
            {"plant_item_id": foreign_item_id, "checked_quantity": 10,
             "growth_status": "good", "check_result": "qualified"},
        ]),
    )
    assert response.status_code == 422
    assert "checks" in response.get_json()["data"]


def test_accept_date_not_before_space_established(api, make_space):
    space = make_space(established_date=date(2026, 1, 1))
    acceptance = create_acceptance(api, space.id)
    response = api.post(
        f"/api/v1/handover-acceptances/{acceptance['id']}/accept",
        accept_payload(acceptance, acceptance_date="2025-12-31"),
    )
    assert response.status_code == 422
    assert "acceptance_date" in response.get_json()["data"]


def test_accept_is_rejected_after_passed(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    response = api.post(
        f"/api/v1/handover-acceptances/{acceptance['id']}/accept",
        accept_payload(acceptance),
    )
    assert response.status_code == 409


# ---------------------------------------------------------------- 整改清单

def test_completing_all_defects_turns_passed(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accepted = accept(api, acceptance, defects=[
        {"description": "草坪局部斑秃", "requirement": "补播草籽", "deadline": "2026-04-01"},
        {"description": "2 株银杏倾斜", "requirement": "扶正加固", "deadline": "2026-04-01"},
    ])
    assert accepted["status"] == "rectifying"
    defect_ids = [item["id"] for item in accepted["defects"]]

    still_open = api.data(api.patch(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{defect_ids[0]}/complete",
        {"finished_date": "2026-03-28", "finished_note": "已补播并覆盖无纺布"},
    ))
    assert still_open["status"] == "rectifying"
    assert still_open["open_defect_count"] == 1

    done = api.data(api.patch(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{defect_ids[1]}/complete",
        {"finished_date": "2026-03-29"},
    ))
    assert done["status"] == "passed"
    assert done["open_defect_count"] == 0
    assert done["warranty_end_date"] == "2028-03-20"


def test_defect_complete_requires_finished_date(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accepted = accept(api, acceptance, defects=[
        {"description": "苗木倾斜", "deadline": "2026-04-01"},
    ])
    defect_id = accepted["defects"][0]["id"]
    response = api.patch(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{defect_id}/complete", {})
    assert response.status_code == 422
    assert "finished_date" in response.get_json()["data"]


def test_defect_cannot_be_completed_twice(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accepted = accept(api, acceptance, defects=[
        {"description": "苗木倾斜", "deadline": "2026-04-01"},
    ])
    defect_id = accepted["defects"][0]["id"]
    url = f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{defect_id}/complete"
    api.data(api.patch(url, {"finished_date": "2026-03-28"}))
    assert api.patch(url, {"finished_date": "2026-03-29"}).status_code == 409


def test_add_defect_after_passed_returns_to_rectifying(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    data = api.data(api.post(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects",
        {"description": "复检发现支撑缺失", "requirement": "补装支撑", "deadline": "2026-04-15"},
    ), 201)
    assert data["status"] == "rectifying"
    assert data["open_defect_count"] == 1


def test_open_defect_can_be_deleted_but_done_cannot(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accepted = accept(api, acceptance, defects=[
        {"description": "误录缺陷", "deadline": "2026-04-01"},
        {"description": "真实缺陷", "deadline": "2026-04-01"},
    ])
    open_id = accepted["defects"][0]["id"]
    done_id = accepted["defects"][1]["id"]
    api.data(api.patch(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{done_id}/complete",
        {"finished_date": "2026-03-28"},
    ))
    # 删除待整改缺陷后，剩余缺陷均已整改，验收单转为通过
    data = api.data(api.delete(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{open_id}"))
    assert data["status"] == "passed"
    assert api.delete(
        f"/api/v1/handover-acceptances/{acceptance['id']}/defects/{done_id}").status_code == 409


def test_defect_must_belong_to_acceptance(api, make_space, make_acceptance):
    acceptance = create_acceptance(api, make_space().id)
    accepted = accept(api, acceptance, defects=[
        {"description": "缺陷", "deadline": "2026-04-01"},
    ])
    other = make_acceptance()
    defect_id = accepted["defects"][0]["id"]
    response = api.patch(
        f"/api/v1/handover-acceptances/{other.id}/defects/{defect_id}/complete",
        {"finished_date": "2026-03-28"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- 质保回访

def test_follow_up_requires_passed_status(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    url = f"/api/v1/handover-acceptances/{acceptance['id']}/follow-ups"
    payload = {"visit_date": "2026-04-01", "issue": "草坪斑秃", "visitor": "周工"}
    assert api.post(url, payload).status_code == 409  # 待验收

    accept(api, acceptance, defects=[{"description": "缺陷", "deadline": "2026-04-10"}])
    assert api.post(url, payload).status_code == 409  # 整改中


def test_follow_up_lifecycle(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    url = f"/api/v1/handover-acceptances/{acceptance['id']}/follow-ups"
    data = api.data(api.post(url, {
        "visit_date": "2026-05-01",
        "issue": "两株银杏叶色发黄",
        "visitor": "周工",
    }), 201)
    follow_up = data["follow_ups"][0]
    assert follow_up["status"] == "open"
    assert follow_up["status_label"] == "处理中"
    assert data["open_follow_up_count"] == 1

    updated = api.data(api.put(f"{url}/{follow_up['id']}", {
        "visit_date": "2026-05-01",
        "issue": "两株银杏叶色发黄",
        "handling": "移交方已追肥复壮，复查叶色转绿",
        "status": "resolved",
        "visitor": "周工",
    }))
    follow_up = updated["follow_ups"][0]
    assert follow_up["status"] == "resolved"
    assert follow_up["handling"] == "移交方已追肥复壮，复查叶色转绿"
    assert updated["open_follow_up_count"] == 0


def test_close_is_blocked_by_open_follow_ups(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    follow_up_url = f"/api/v1/handover-acceptances/{acceptance['id']}/follow-ups"
    created = api.data(api.post(follow_up_url, {"visit_date": "2026-05-01", "issue": "苗木倾斜"}), 201)
    follow_up_id = created["follow_ups"][0]["id"]

    close_url = f"/api/v1/handover-acceptances/{acceptance['id']}/close"
    assert api.post(close_url).status_code == 409  # 回访问题未解决

    api.data(api.put(f"{follow_up_url}/{follow_up_id}", {
        "visit_date": "2026-05-01", "issue": "苗木倾斜",
        "handling": "已扶正", "status": "resolved",
    }))
    closed = api.data(api.post(close_url))
    assert closed["status"] == "closed"
    assert closed["status_label"] == "已办结"
    assert api.post(close_url).status_code == 409  # 不可重复办结


def test_closed_acceptance_is_readonly(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    api.data(api.post(f"/api/v1/handover-acceptances/{acceptance['id']}/close"))

    base = f"/api/v1/handover-acceptances/{acceptance['id']}"
    payload = acceptance_payload(make_space().id)
    payload.pop("plants")
    assert api.put(base, payload).status_code == 409
    assert api.post(f"{base}/defects",
                    {"description": "新缺陷", "deadline": "2026-05-01"}).status_code == 409
    assert api.post(f"{base}/follow-ups",
                    {"visit_date": "2026-05-01", "issue": "问题"}).status_code == 409


# ---------------------------------------------------------------- 更新与删除

def test_plant_list_only_editable_while_pending(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    new_plants = [{"plant_name": "香樟", "quantity": 20, "unit": "plant"}]
    updated = api.data(api.put(
        f"/api/v1/handover-acceptances/{acceptance['id']}",
        acceptance_payload(make_space().id, plants=new_plants),
    ))
    assert len(updated["plant_items"]) == 1
    assert updated["plant_items"][0]["plant_name"] == "香樟"

    accept(api, updated)
    response = api.put(
        f"/api/v1/handover-acceptances/{acceptance['id']}",
        acceptance_payload(make_space().id, plants=new_plants),
    )
    assert response.status_code == 422
    assert "plants" in response.get_json()["data"]


def test_warranty_end_date_recomputed_after_warranty_change(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance)
    payload = acceptance_payload(make_space().id, warranty_months=36)
    payload.pop("plants")
    updated = api.data(api.put(f"/api/v1/handover-acceptances/{acceptance['id']}", payload))
    assert updated["warranty_end_date"] == "2029-03-20"


def test_delete_is_blocked_until_force(api, make_space):
    acceptance = create_acceptance(api, make_space().id)
    accept(api, acceptance, defects=[{"description": "缺陷", "deadline": "2026-04-01"}])

    response = api.delete(f"/api/v1/handover-acceptances/{acceptance['id']}")
    assert response.status_code == 409
    details = response.get_json()["data"]
    assert details["plant_item"] == 2
    assert details["defect"] == 1

    api.data(api.delete(f"/api/v1/handover-acceptances/{acceptance['id']}", force="true"))
    assert api.get(f"/api/v1/handover-acceptances/{acceptance['id']}").status_code == 404


def test_green_space_delete_protection_counts_acceptances(api, make_space):
    space = make_space()
    acceptance = create_acceptance(api, space.id)
    response = api.delete(f"/api/v1/green-spaces/{space.id}")
    assert response.status_code == 409
    assert response.get_json()["data"]["handover_acceptance"] == 1

    data = api.data(api.delete(f"/api/v1/green-spaces/{space.id}", force="true"))
    assert data["handover_acceptance"] == 1
    assert api.get(f"/api/v1/handover-acceptances/{acceptance['id']}").status_code == 404


# ---------------------------------------------------------------- 列表与汇总

def test_list_filters_and_summary(api, make_space):
    space = make_space()
    pending = create_acceptance(api, space.id, handover_party="甲建设单位")
    rectifying = create_acceptance(api, space.id, handover_party="乙建设单位")
    accept(api, rectifying, defects=[{"description": "缺陷", "deadline": "2026-04-01"}])
    passed = create_acceptance(api, space.id, handover_party="丙建设单位")
    accept(api, passed)

    data = api.data(api.get("/api/v1/handover-acceptances", green_space_id=space.id))
    assert data["meta"]["total"] == 3
    summary = data["summary"]
    assert summary["total_count"] == 3
    assert summary["by_status"] == {"pending": 1, "rectifying": 1, "passed": 1, "closed": 0}
    assert summary["open_defect_count"] == 1

    by_status = api.data(api.get("/api/v1/handover-acceptances", status="rectifying"))
    assert by_status["meta"]["total"] == 1
    assert by_status["items"][0]["id"] == rectifying["id"]

    by_keyword = api.data(api.get("/api/v1/handover-acceptances", keyword="乙建设"))
    assert by_keyword["meta"]["total"] == 1

    with_open_defect = api.data(api.get("/api/v1/handover-acceptances", defect_open="true"))
    assert with_open_defect["meta"]["total"] == 1
    assert with_open_defect["items"][0]["id"] == rectifying["id"]


def test_seeded_acceptances_are_consistent(api, seeded):
    assert seeded["handover_acceptance"] == 3
    data = api.data(api.get("/api/v1/handover-acceptances", page_size=50))
    assert data["meta"]["total"] == 3
    by_status = data["summary"]["by_status"]
    assert by_status["pending"] == 1
    assert by_status["rectifying"] == 1
    assert by_status["passed"] == 1
    # 质保中的验收单带两条回访，其中一条处理中
    passed = next(item for item in data["items"] if item["status"] == "passed")
    assert passed["follow_up_count"] == 2
    assert passed["open_follow_up_count"] == 1
    assert passed["warranty_end_date"] is not None
