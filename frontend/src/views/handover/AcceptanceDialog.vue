<template>
  <el-dialog :model-value="visible" title="现场验收核对" width="980px" top="4vh"
             destroy-on-close @update:model-value="close">
    <div v-loading="loading">
      <el-form label-width="100px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="验收日期" required :error="fieldErrors.acceptance_date">
              <el-date-picker v-model="form.acceptance_date" type="date" value-format="YYYY-MM-DD"
                              style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="验收人" required :error="fieldErrors.inspector">
              <el-input v-model="form.inspector" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="实测面积" :error="fieldErrors.checked_area_sqm">
              <el-input-number v-model="form.checked_area_sqm" :min="0" :max="99999999"
                               :precision="2" :controls="false" :disabled="isReject"
                               placeholder="通过时必填" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="section-title">逐项核对（面积 / 数量 / 长势）</div>
      <el-table :data="form.items" border size="small">
        <el-table-column type="index" label="#" width="42" />
        <el-table-column label="苗木" min-width="150">
          <template #default="{ row }">
            <div>{{ row.plant_name }}</div>
            <div class="cell-sub">{{ row.plant_category_label }} · {{ row.spec || '无规格' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="登记数量" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.quantity) }} {{ row.unit_label }}
          </template>
        </el-table-column>
        <el-table-column label="核对数量" width="130">
          <template #default="{ row, $index }">
            <el-input-number v-model="row.checked_quantity" :min="0" :max="99999999"
                             :precision="2" :controls="false" :disabled="isReject"
                             :class="{ 'row-invalid': rowError($index, 'checked_quantity') }"
                             style="width: 100%" />
            <div v-if="rowError($index, 'checked_quantity')" class="row-error">
              {{ rowError($index, 'checked_quantity') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="长势" width="120">
          <template #default="{ row, $index }">
            <el-select v-model="row.growth_condition" :disabled="isReject" placeholder="选择"
                       :class="{ 'row-invalid': rowError($index, 'growth_condition') }">
              <el-option v-for="item in growthOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
            <div v-if="rowError($index, 'growth_condition')" class="row-error">
              {{ rowError($index, 'growth_condition') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="核对结论" width="116">
          <template #default="{ row, $index }">
            <el-select v-model="row.check_result" :disabled="isReject" placeholder="选择"
                       :class="{ 'row-invalid': rowError($index, 'check_result') }">
              <el-option v-for="item in checkOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
            <div v-if="rowError($index, 'check_result')" class="row-error">
              {{ rowError($index, 'check_result') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.remark" :disabled="isReject" maxlength="500" />
          </template>
        </el-table-column>
      </el-table>
      <div v-if="fieldErrors.items" class="table-error">{{ fieldErrors.items }}</div>

      <div class="section-title">
        缺陷整改清单
        <el-button v-if="!isReject" link type="primary" :icon="'Plus'"
                   @click="addDefect">新增缺陷</el-button>
      </div>
      <el-table :data="form.defects" border size="small" empty-text="无缺陷，验收通过后直接接管">
        <el-table-column type="index" label="#" width="42" />
        <el-table-column label="缺陷描述" min-width="180">
          <template #default="{ row, $index }">
            <el-input v-model="row.description" type="textarea" :rows="1" maxlength="500"
                      :class="{ 'row-invalid': defectError($index, 'description') }" />
            <div v-if="defectError($index, 'description')" class="row-error">
              {{ defectError($index, 'description') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="位置" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.location" maxlength="128" />
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="106">
          <template #default="{ row }">
            <el-select v-model="row.severity">
              <el-option v-for="item in severityOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="整改期限" width="150">
          <template #default="{ row, $index }">
            <el-date-picker v-model="row.deadline" type="date" value-format="YYYY-MM-DD"
                            :class="{ 'row-invalid': defectError($index, 'deadline') }"
                            style="width: 100%" />
            <div v-if="defectError($index, 'deadline')" class="row-error">
              {{ defectError($index, 'deadline') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="责任单位/人" min-width="130">
          <template #default="{ row }">
            <el-input v-model="row.responsible" maxlength="96" />
          </template>
        </el-table-column>
        <el-table-column label="" width="46">
          <template #default="{ $index }">
            <el-button link type="danger" :icon="'Delete'"
                       @click="form.defects.splice($index, 1)" />
          </template>
        </el-table-column>
      </el-table>
      <div v-if="fieldErrors.defects" class="table-error">{{ fieldErrors.defects }}</div>

      <el-form label-width="100px" style="margin-top: 12px">
        <el-form-item label="验收意见" :error="fieldErrors.conclusion">
          <el-input v-model="form.conclusion" type="textarea" :rows="2" maxlength="2000"
                    placeholder="现场验收情况与整改要求" />
        </el-form-item>
        <el-form-item label="验收结论" required>
          <el-radio-group v-model="form.verdict">
            <el-radio value="pass">验收通过（有缺陷时转整改，闭环后接管）</el-radio>
            <el-radio value="reject">验收不通过（退回整改后重新报验）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交验收结果</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { formatNumber, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: growthOptions } = useEnumOptions('growth_condition')
const { options: checkOptions } = useEnumOptions('plant_check_result')
const { options: severityOptions } = useEnumOptions('defect_severity')

const visible = ref(false)
const loading = ref(false)
const submitting = ref(false)
const handoverId = ref(null)
const fieldErrors = ref({})
const form = reactive(emptyForm())

const isReject = computed(() => form.verdict === 'reject')

function emptyForm() {
  return {
    acceptance_date: today(),
    inspector: '',
    checked_area_sqm: null,
    conclusion: '',
    verdict: 'pass',
    items: [],
    defects: [],
  }
}

function rowError(index, field) {
  return fieldErrors.value[`items[${index}].${field}`]
}

function defectError(index, field) {
  return fieldErrors.value[`defects[${index}].${field}`]
}

function addDefect() {
  form.defects.push({ description: '', location: '', severity: 'general', deadline: '', responsible: '' })
}

async function open(id) {
  handoverId.value = id
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  visible.value = true
  loading.value = true
  try {
    const detail = await handoverAcceptanceApi.detail(id)
    form.inspector = detail.inspector || ''
    form.checked_area_sqm = detail.checked_area_sqm
    form.items = (detail.plant_items || []).map((item) => ({
      id: item.id,
      plant_name: item.plant_name,
      plant_category_label: item.plant_category_label,
      spec: item.spec,
      quantity: item.quantity,
      unit_label: item.unit_label,
      checked_quantity: item.checked_quantity,
      growth_condition: item.growth_condition,
      check_result: item.check_result,
      remark: item.remark || '',
    }))
  } finally {
    loading.value = false
  }
}

function close() {
  visible.value = false
}

async function submit() {
  submitting.value = true
  fieldErrors.value = {}
  const payload = {
    acceptance_date: form.acceptance_date,
    inspector: form.inspector,
    verdict: form.verdict,
    conclusion: form.conclusion || null,
  }
  if (form.verdict === 'pass') {
    payload.checked_area_sqm = form.checked_area_sqm
    payload.items = form.items.map((item) => ({
      id: item.id,
      checked_quantity: item.checked_quantity,
      growth_condition: item.growth_condition,
      check_result: item.check_result,
      remark: item.remark || null,
    }))
    payload.defects = form.defects.map((row) => ({
      description: row.description,
      location: row.location || null,
      severity: row.severity,
      deadline: row.deadline,
      responsible: row.responsible || null,
    }))
  } else {
    payload.items = []
    payload.defects = []
  }

  try {
    await handoverAcceptanceApi.accept(handoverId.value, payload)
    ElMessage.success('验收结果已提交')
    emit('saved')
    close()
  } catch (error) {
    fieldErrors.value = error?.details || {}
  } finally {
    submitting.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  margin: 14px 0 8px;
}

.cell-sub {
  color: #909399;
  font-size: 12px;
}

.row-invalid :deep(.el-input__wrapper),
.row-invalid :deep(.el-select__wrapper),
.row-invalid :deep(.el-date-editor) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}

.row-error {
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.4;
  padding-top: 2px;
}

.table-error {
  color: var(--el-color-danger);
  font-size: 12px;
  margin-top: 4px;
}
</style>
