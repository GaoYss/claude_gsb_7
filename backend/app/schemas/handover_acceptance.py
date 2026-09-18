"""绿地移交验收校验规则。

验收单本体用链式校验器；苗木清单、核对结果、整改清单为嵌套数组，
逐行用独立校验器校验，错误以「plants.0.plant_name」形式汇总返回。
"""

from ..constants import (
    FOLLOW_UP_STATUS,
    GROWTH_STATUS,
    ITEM_CHECK_RESULT,
    MEASURE_UNIT,
    PLANT_CATEGORY,
)
from ..errors import ValidationError
from .common import PayloadValidator


def _validate_rows(payload, key, row_label, validate_row, *, required=False, max_rows=200):
    """校验嵌套数组，返回清洗后的列表；错误键带行号便于前端定位。"""

    rows = payload.get(key)
    if rows is None:
        if required:
            raise ValidationError(
                "提交的数据未通过校验", details={key: f"{row_label}不能为空"}
            )
        return None
    if not isinstance(rows, list):
        raise ValidationError(
            "提交的数据未通过校验", details={key: f"{row_label}必须是数组"}
        )
    if required and not rows:
        raise ValidationError(
            "提交的数据未通过校验", details={key: f"{row_label}至少填写一行"}
        )
    if len(rows) > max_rows:
        raise ValidationError(
            "提交的数据未通过校验",
            details={key: f"{row_label}一次最多提交 {max_rows} 行"},
        )

    clean_rows = []
    errors = {}
    for index, row in enumerate(rows):
        try:
            clean_rows.append(validate_row(row if isinstance(row, dict) else {}))
        except ValidationError as exc:
            for field, message in (exc.details or {}).items():
                errors[f"{key}.{index}.{field}"] = message
    if errors:
        raise ValidationError("提交的数据未通过校验", details=errors)
    return clean_rows


def _validate_plant_row(row):
    return (
        PayloadValidator(row)
        .string("plant_name", "苗木名称", required=True, max_length=96)
        .enum("plant_category", "植物类别", group=PLANT_CATEGORY, default="tree")
        .string("spec", "规格", max_length=64)
        .number("quantity", "清单数量", required=True, min_value=0.01, max_value=9999999)
        .enum("unit", "计量单位", group=MEASURE_UNIT, default="plant")
        .done()
    )


def _validate_check_row(row):
    return (
        PayloadValidator(row)
        .integer("plant_item_id", "苗木清单行", required=True, min_value=1)
        .number("checked_quantity", "实核数量", min_value=0, max_value=9999999)
        .enum("growth_status", "长势", group=GROWTH_STATUS)
        .enum("check_result", "核对结论", group=ITEM_CHECK_RESULT, required=True)
        .done()
    )


def _validate_defect_row(row):
    return (
        PayloadValidator(row)
        .string("description", "缺陷描述", required=True, max_length=255)
        .string("requirement", "整改要求", max_length=255)
        .date("deadline", "完成期限", required=True)
        .done()
    )


def validate_handover_acceptance(payload):
    """验收单登记/更新：本体字段 + 苗木清单（plants）。"""

    data = (
        PayloadValidator(payload)
        .integer("green_space_id", "所属绿地", required=True, min_value=1)
        .string("handover_party", "移交方", required=True, max_length=128)
        .string("receiver", "接收单位", max_length=128)
        .number("area_sqm", "绿化面积", required=True, min_value=0.01, max_value=99999999)
        .integer("warranty_months", "质保期（月）", required=True, min_value=1, max_value=120)
        .string("inspector", "验收人", max_length=64)
        .text("remark", "备注", max_length=2000)
        .done()
    )
    plants = _validate_rows(payload, "plants", "苗木清单", _validate_plant_row, max_rows=500)
    if plants is not None:
        data["plants"] = plants
    return data


def validate_acceptance_accept(payload):
    """验收登记：验收结论 + 逐项核对结果（checks）+ 缺陷整改清单（defects）。"""

    data = (
        PayloadValidator(payload)
        .date("acceptance_date", "验收日期", required=True)
        .number("measured_area_sqm", "实测面积", required=True, min_value=0, max_value=99999999)
        .string("inspector", "验收人", max_length=64)
        .done()
    )
    checks = _validate_rows(payload, "checks", "核对结果", _validate_check_row, max_rows=500)
    if checks is not None:
        data["checks"] = checks
    defects = _validate_rows(payload, "defects", "整改清单", _validate_defect_row)
    if defects is not None:
        data["defects"] = defects
    return data


def validate_acceptance_defect(payload):
    return _validate_defect_row(payload)


def validate_defect_complete(payload):
    return (
        PayloadValidator(payload)
        .date("finished_date", "完成日期", required=True)
        .string("finished_note", "复核说明", max_length=255)
        .done()
    )


def validate_acceptance_follow_up(payload):
    return (
        PayloadValidator(payload)
        .date("visit_date", "回访日期", required=True)
        .string("issue", "问题描述", required=True, max_length=255)
        .string("handling", "处理情况", max_length=255)
        .enum("status", "处理状态", group=FOLLOW_UP_STATUS, default="open")
        .string("visitor", "回访人", max_length=64)
        .done()
    )
