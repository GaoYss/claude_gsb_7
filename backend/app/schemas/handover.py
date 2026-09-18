"""绿地移交验收校验规则。

PayloadValidator 只支持扁平字段，苗木清单/核对项/缺陷清单等嵌套数组
在本文件内逐行复用 PayloadValidator 校验，错误键形如 ``plant_items[0].plant_name``，
便于前端挂到对应行的对应字段。
"""

from ..constants import (
    DEFECT_SEVERITY,
    DEFECT_STATUS,
    GROWTH_CONDITION,
    HANDOVER_VERDICT,
    MEASURE_UNIT,
    PLANT_CATEGORY,
    PLANT_CHECK_RESULT,
    REVISIT_RESULT,
)
from ..utils.dates import today
from .common import PayloadValidator


# ------------------------------------------------------------ 嵌套数组工具
def _collect_rows(validator, raw, key, row_builder, *, required=False, min_rows=1):
    """把 raw[key] 数组逐行校验并入 validator，行错误写入 validator.errors。"""

    if key not in raw:
        if required:
            validator.errors.setdefault(key, "苗木清单不能为空")
        return
    rows = raw[key]
    if not isinstance(rows, list):
        validator.errors.setdefault(key, "苗木清单必须是数组")
        return
    if len(rows) < min_rows:
        validator.errors.setdefault(key, f"苗木清单至少保留 {min_rows} 行")
        return

    clean_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            validator.errors.setdefault(f"{key}[{index}]", "该行必须是对象")
            continue
        row_validator = row_builder(row)
        if row_validator.errors:
            for field, message in row_validator.errors.items():
                validator.errors.setdefault(f"{key}[{index}].{field}", message)
        else:
            clean_rows.append(row_validator.clean)
    validator.clean[key] = clean_rows


# ------------------------------------------------------------ 登记/改单
def _plant_item_validator(row):
    return (
        PayloadValidator(row)
        .string("plant_name", "苗木名称", required=True, max_length=96)
        .enum("plant_category", "植物类别", group=PLANT_CATEGORY, required=True)
        .string("spec", "规格", max_length=64)
        .number("quantity", "登记数量", required=True, min_value=0.01, max_value=99999999)
        .enum("unit", "计量单位", group=MEASURE_UNIT, default="plant")
        .text("remark", "备注", max_length=500)
    )


def validate_handover(payload, *, require_items=True):
    """登记/改单校验。create 要求苗木清单至少 1 行；update 仅当键出现才替换。"""

    validator = (
        PayloadValidator(payload)
        .string("handover_no", "验收单编号", max_length=32)
        .integer("green_space_id", "所属绿地", required=True, min_value=1)
        .string("transferor", "移交单位", required=True, max_length=128)
        .string("receiver", "接管养护单位", max_length=128)
        .date("handover_date", "移交日期", required=True)
        .number("area_sqm", "登记绿化面积", required=True, min_value=0.01, max_value=99999999)
        .integer("warranty_months", "质保期月数", default=12, min_value=1, max_value=120)
        .string("inspector", "验收人", max_length=64)
        .text("remark", "备注", max_length=2000)
    )
    _collect_rows(
        validator, payload, "plant_items", _plant_item_validator, required=require_items
    )
    if validator.errors:
        from ..errors import ValidationError

        raise ValidationError("提交的数据未通过校验", details=validator.errors)
    return validator.clean


# ------------------------------------------------------------ 验收
def _acceptance_item_validator(row):
    return (
        PayloadValidator(row)
        .integer("id", "苗木行", required=True, min_value=1)
        .number("checked_quantity", "核对数量", min_value=0, max_value=99999999)
        .enum("growth_condition", "长势", group=GROWTH_CONDITION)
        .enum("check_result", "核对结论", group=PLANT_CHECK_RESULT)
        .text("remark", "备注", max_length=500)
    )


def _defect_row_validator(row):
    return (
        PayloadValidator(row)
        .text("description", "缺陷描述", required=True, max_length=500)
        .string("location", "缺陷位置", max_length=128)
        .enum("severity", "严重程度", group=DEFECT_SEVERITY, default="general")
        .date("deadline", "整改期限", required=True)
        .string("responsible", "责任单位/人", max_length=96)
    )


def validate_acceptance(payload):
    """现场验收：逐项核对结果 + 新发现缺陷清单 + 验收结论。"""

    validator = (
        PayloadValidator(payload)
        .date("acceptance_date", "验收日期")
        .string("inspector", "验收人", required=True, max_length=64)
        .number("checked_area_sqm", "实测绿化面积", min_value=0, max_value=99999999)
        .enum("verdict", "验收结论", group=HANDOVER_VERDICT, required=True)
        .text("conclusion", "验收意见", max_length=2000)
    )
    _collect_rows(validator, payload, "items", _acceptance_item_validator, min_rows=0)
    # 缺陷清单的行错误键与缺陷实体的字段错误保持同一前缀
    if "defects" in payload:
        raw = payload["defects"]
        if not isinstance(raw, list):
            validator.errors.setdefault("defects", "缺陷清单必须是数组")
        else:
            clean_rows = []
            for index, row in enumerate(raw):
                if not isinstance(row, dict):
                    validator.errors.setdefault(f"defects[{index}]", "该行必须是对象")
                    continue
                row_validator = _defect_row_validator(row)
                if row_validator.errors:
                    for field, message in row_validator.errors.items():
                        validator.errors.setdefault(f"defects[{index}].{field}", message)
                else:
                    clean_rows.append(row_validator.clean)
            validator.clean["defects"] = clean_rows
    validator.clean.setdefault("items", [])
    validator.clean.setdefault("defects", [])
    validator.clean.setdefault("acceptance_date", today())

    if validator.errors:
        from ..errors import ValidationError

        raise ValidationError("提交的数据未通过校验", details=validator.errors)
    return validator.clean


# ------------------------------------------------------------ 缺陷/回访
def validate_defect(payload):
    """缺陷登记：描述与期限必填。"""

    return (
        PayloadValidator(payload)
        .text("description", "缺陷描述", required=True, max_length=500)
        .string("location", "缺陷位置", max_length=128)
        .enum("severity", "严重程度", group=DEFECT_SEVERITY)
        .date("deadline", "整改期限", required=True)
        .string("responsible", "责任单位/人", max_length=96)
        .text("recheck_note", "复验情况", max_length=1000)
        .text("remark", "备注", max_length=500)
        .done()
    )


def validate_defect_update(payload):
    """缺陷整改更新：字段均可选（允许只推进状态），服务端做状态机校验。"""

    return (
        PayloadValidator(payload)
        .text("description", "缺陷描述", max_length=500)
        .string("location", "缺陷位置", max_length=128)
        .enum("severity", "严重程度", group=DEFECT_SEVERITY)
        .date("deadline", "整改期限")
        .string("responsible", "责任单位/人", max_length=96)
        .enum("status", "整改状态", group=DEFECT_STATUS)
        .text("recheck_note", "复验情况", max_length=1000)
        .text("remark", "备注", max_length=500)
        .done()
    )


def validate_completion(payload):
    """复验闭环：仅可补充验收意见。"""

    return (
        PayloadValidator(payload)
        .text("conclusion", "验收意见", max_length=2000)
        .done()
    )


def validate_revisit(payload):
    """质保期回访登记。result 缺省由模型默认 normal，PUT 缺省时保留原值。"""

    return (
        PayloadValidator(payload)
        .date("visit_date", "回访日期", required=True)
        .string("visitor", "回访人", max_length=64)
        .number("survival_rate", "苗木成活率", min_value=0, max_value=100, digits=1)
        .text("issue", "发现问题", max_length=1000)
        .text("handling", "处理情况", max_length=1000)
        .enum("result", "回访结果", group=REVISIT_RESULT)
        .date("next_visit_date", "计划下次回访日期")
        .text("remark", "备注", max_length=500)
        .done()
    )
