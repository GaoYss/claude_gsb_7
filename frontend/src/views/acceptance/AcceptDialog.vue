<template>
  <el-dialog :model-value="visible" title="验收登记" width="920px" top="4vh"
             destroy-on-close @update:model-value="close">
    <el-alert v-if="acceptance" type="info" :closable="false" class="accept-tip">
      验收单 {{ acceptance.acceptance_no }} · 登记面积 {{ formatArea(acceptance.area_sqm) }} ·
      请逐项核对苗木数量与长势，发现的缺陷将形成整改清单
    </el-alert>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="验收日期" prop="acceptance_date" :error="fieldErrors.acceptance_date">
            <el-date-picker v-model="form.acceptance_date" type="date" value-format="YYYY-MM-DD"
                            placeholder="选择日期" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="实测面积（㎡）" prop="measured_area_sqm" :error="fieldErrors.measured_area_sqm">
            <el-input-number v-model="form.measured_area_sqm" :min="0" :max="99999999" :precision="2"
                             :controls="false" placeholder="现场实测" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="验收人" :error="fieldErrors.inspector">
            <el-input v-model="form.inspector" maxlength="64" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="逐项核对">
        <el-table :data="checks" border size="small" class="check-table">
          <el-table-column label="苗木名称" min-width="130">
            <template #default="{ row }">
              <div>{{ row.plant_name }}</div>
              <span class="check-table__spec">{{ row.spec || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="清单数量" width="110" align="right">
            <template #default="{ row }">{{ formatNumber(row.quantity) }} {{ row.unit_label }}</template>
          </el-table-column>
          <el-table-column label="实核数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.checked_quantity" :min="0" :max="9999999"
                               :precision="2" :controls="false" placeholder="实核" size="small"
                               style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="长势" width="130">
            <template #default="{ row }">
              <el-select v-model="row.growth_status" size="small" placeholder="选择长势">
                <el-option v-for="item in growthOptions" :key="item.value"
                           :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="核对结论" width="120">
            <template #default="{ row }">
              <el-select v-model="row.check_result" size="small">
                <el-option v-for="item in checkResultOptions" :key="item.value"
                           :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="fieldErrors.checks" class="field-error">{{ fieldErrors.checks }}</div>
      </el-form-item>

      <el-form-item label="整改清单">
        <div class="defect-list">
          <div v-for="(row, index) in defects" :key="index" class="defect-list__row">
            <el-input v-model="row.description" placeholder="缺陷描述，如：3 株樱花死亡" maxlength="255" />
            <el-input v-model="row.requirement" placeholder="整改要求（选填）" maxlength="255" />
            <el-date-picker v-model="row.deadline" type="date" value-format="YYYY-MM-DD"
                            placeholder="完成期限" style="width: 150px" />
            <el-button link type="danger" :icon="'Delete'" @click="defects.splice(index, 1)" />
          </div>
          <el-button link type="primary" :icon="'Plus'" @click="addDefect">添加缺陷</el-button>
          <div v-if="defectErrors.length" class="field-error">
            <div v-for="(message, key) in defectErrors" :key="key">{{ message }}</div>
          </div>
        </div>
      </el-form-item>
    </el-form>

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
import { formatArea, formatNumber, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: growthOptions } = useEnumOptions('growth_status')
const { options: checkResultOptions } = useEnumOptions('item_check_result')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const acceptance = ref(null)
const fieldErrors = ref({})
const checks = ref([])
const defects = ref([])
const form = reactive({ acceptance_date: '', measured_area_sqm: null, inspector: '' })

const rules = {
  acceptance_date: [{ required: true, message: '请选择验收日期', trigger: 'change' }],
  measured_area_sqm: [{ required: true, message: '请输入实测面积', trigger: 'blur' }],
}

const defectErrors = computed(() => {
  const messages = {}
  Object.entries(fieldErrors.value || {})
    .filter(([key]) => key.startsWith('defects.'))
    .forEach(([key, message]) => {
      const rowNo = Number(key.split('.')[1]) + 1
      messages[key] = `第 ${rowNo} 行：${message}`
    })
  return messages
})

function addDefect() {
  defects.value.push({ description: '', requirement: '', deadline: '' })
}

function open(row) {
  acceptance.value = row
  fieldErrors.value = {}
  form.acceptance_date = row.acceptance_date || today()
  form.measured_area_sqm = row.measured_area_sqm ?? row.area_sqm ?? null
  form.inspector = row.inspector || ''
  checks.value = (row.plant_items || []).map((item) => ({
    plant_item_id: item.id,
    plant_name: item.plant_name,
    spec: item.spec,
    quantity: item.quantity,
    unit_label: item.unit_label,
    checked_quantity: item.checked_quantity ?? item.quantity,
    growth_status: item.growth_status || 'good',
    check_result: item.check_result && item.check_result !== 'unchecked' ? item.check_result : 'qualified',
  }))
  defects.value = []
  visible.value = true
}

function close() {
  visible.value = false
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  fieldErrors.value = {}
  const payload = {
    acceptance_date: form.acceptance_date,
    measured_area_sqm: form.measured_area_sqm,
    inspector: form.inspector || null,
    checks: checks.value.map((row) => ({
      plant_item_id: row.plant_item_id,
      checked_quantity: row.checked_quantity,
      growth_status: row.growth_status || null,
      check_result: row.check_result,
    })),
    defects: defects.value
      .filter((row) => row.description && row.description.trim())
      .map((row) => ({
        description: row.description.trim(),
        requirement: row.requirement?.trim() || null,
        deadline: row.deadline || null,
      })),
  }
  try {
    await handoverAcceptanceApi.accept(acceptance.value.id, payload)
    ElMessage.success('验收登记完成')
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
.accept-tip {
  margin-bottom: 16px;
}

.check-table {
  width: 100%;
}

.check-table__spec {
  color: #909399;
  font-size: 12px;
}

.defect-list {
  width: 100%;
}

.defect-list__row {
  display: grid;
  grid-template-columns: 1.4fr 1.2fr 150px 32px;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.field-error {
  color: #f56c6c;
  font-size: 12px;
  line-height: 1.6;
  margin-top: 4px;
}
</style>
