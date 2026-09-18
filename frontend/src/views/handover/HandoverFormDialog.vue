<template>
  <el-dialog :model-value="visible"
             :title="isEdit ? `编辑移交验收单 · ${form.handover_no}` : '登记绿地移交验收'"
             width="880px" top="5vh" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="所属绿地" prop="green_space_id" :error="fieldErrors.green_space_id">
            <GreenSpaceSelect v-model="form.green_space_id" :preset="spacePreset"
                              :disabled="isEdit" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="移交日期" prop="handover_date" :error="fieldErrors.handover_date">
            <el-date-picker v-model="form.handover_date" type="date" value-format="YYYY-MM-DD"
                            placeholder="选择移交日期" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="移交单位" prop="transferor" :error="fieldErrors.transferor">
            <el-input v-model="form.transferor" placeholder="如：城建园林建设公司" maxlength="128" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="接管单位" :error="fieldErrors.receiver">
            <el-input v-model="form.receiver" placeholder="如：区市政养护中心" maxlength="128" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="绿化面积" prop="area_sqm" :error="fieldErrors.area_sqm">
            <el-input-number v-model="form.area_sqm" :min="0.01" :max="99999999" :precision="2"
                             :controls="false" placeholder="登记绿化面积" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="质保期" prop="warranty_months" :error="fieldErrors.warranty_months">
            <el-input-number v-model="form.warranty_months" :min="1" :max="120" :step="1"
                             style="width: 100%" />
            <span class="unit-suffix">个月</span>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="验收人" :error="fieldErrors.inspector">
            <el-input v-model="form.inspector" placeholder="可留待现场验收时填写" maxlength="64" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="苗木清单" required :error="fieldErrors.plant_items">
        <div class="sub-table">
          <el-table :data="form.plant_items" border size="small">
            <el-table-column type="index" label="#" width="42" />
            <el-table-column label="苗木名称" min-width="130">
              <template #default="{ row, $index }">
                <el-input v-model="row.plant_name" placeholder="如：香樟" maxlength="96"
                          :class="{ 'row-invalid': rowError($index, 'plant_name') }" />
                <div v-if="rowError($index, 'plant_name')" class="row-error">
                  {{ rowError($index, 'plant_name') }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="类别" width="120">
              <template #default="{ row, $index }">
                <el-select v-model="row.plant_category" placeholder="类别"
                           :class="{ 'row-invalid': rowError($index, 'plant_category') }">
                  <el-option v-for="item in categoryOptions" :key="item.value"
                             :label="item.label" :value="item.value" />
                </el-select>
                <div v-if="rowError($index, 'plant_category')" class="row-error">
                  {{ rowError($index, 'plant_category') }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="规格" min-width="120">
              <template #default="{ row }">
                <el-input v-model="row.spec" placeholder="如：胸径 15cm" maxlength="64" />
              </template>
            </el-table-column>
            <el-table-column label="数量" width="120">
              <template #default="{ row, $index }">
                <el-input-number v-model="row.quantity" :min="0" :max="99999999" :precision="2"
                                 :controls="false" style="width: 100%"
                                 :class="{ 'row-invalid': rowError($index, 'quantity') }" />
                <div v-if="rowError($index, 'quantity')" class="row-error">
                  {{ rowError($index, 'quantity') }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="单位" width="96">
              <template #default="{ row }">
                <el-select v-model="row.unit">
                  <el-option v-for="item in unitOptions" :key="item.value"
                             :label="item.label" :value="item.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="" width="46">
              <template #default="{ $index }">
                <el-button link type="danger" :icon="'Delete'"
                           @click="form.plant_items.splice($index, 1)" />
              </template>
            </el-table-column>
          </el-table>
          <el-button class="sub-table__add" :icon="'Plus'" text type="primary"
                     @click="addItem">添加苗木</el-button>
          <div class="form-hint">验收时将按清单逐项核对数量与长势，至少保留 1 行苗木。</div>
        </div>
      </el-form-item>

      <el-form-item label="备注" :error="fieldErrors.remark">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="2000" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import GreenSpaceSelect from '@/components/common/GreenSpaceSelect.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: categoryOptions } = useEnumOptions('plant_category')
const { options: unitOptions } = useEnumOptions('measure_unit')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const fieldErrors = ref({})
const spacePreset = ref(null)
const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value !== null)

const rules = {
  green_space_id: [{ required: true, message: '请选择所属绿地', trigger: 'change' }],
  transferor: [{ required: true, message: '请输入移交单位', trigger: 'blur' }],
  handover_date: [{ required: true, message: '请选择移交日期', trigger: 'change' }],
  area_sqm: [{ required: true, message: '请输入登记绿化面积', trigger: 'blur' }],
  warranty_months: [{ required: true, message: '请填写质保期月数', trigger: 'blur' }],
}

function emptyForm() {
  return {
    handover_no: '',
    green_space_id: null,
    transferor: '',
    receiver: '',
    handover_date: today(),
    area_sqm: null,
    warranty_months: 12,
    inspector: '',
    remark: '',
    plant_items: [],
  }
}

function emptyItem() {
  return { plant_name: '', plant_category: 'tree', spec: '', quantity: null, unit: 'plant' }
}

function addItem() {
  form.plant_items.push(emptyItem())
}

function rowError(index, field) {
  return fieldErrors.value[`plant_items[${index}].${field}`]
}

async function open(row = null, presetSpace = null) {
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  spacePreset.value = null
  editingId.value = row?.id ?? null

  if (presetSpace) {
    form.green_space_id = presetSpace.id
    spacePreset.value = { ...presetSpace }
  }
  if (row) {
    let detail = row
    if (!Array.isArray(row.plant_items)) {
      detail = await handoverAcceptanceApi.detail(row.id)
    }
    Object.keys(form).forEach((key) => {
      if (detail[key] !== undefined && key !== 'plant_items') form[key] = detail[key]
    })
    form.plant_items = (detail.plant_items || []).map((item) => ({
      plant_name: item.plant_name,
      plant_category: item.plant_category,
      spec: item.spec || '',
      quantity: item.quantity,
      unit: item.unit,
    }))
    spacePreset.value = detail.green_space || null
  }
  if (!form.plant_items.length) addItem()
  visible.value = true
}

function close() {
  visible.value = false
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!form.plant_items.length) {
    fieldErrors.value.plant_items = '苗木清单至少保留 1 行'
    return
  }
  submitting.value = true
  fieldErrors.value = {}
  const payload = {
    green_space_id: form.green_space_id,
    transferor: form.transferor,
    receiver: form.receiver || null,
    handover_date: form.handover_date,
    area_sqm: form.area_sqm,
    warranty_months: form.warranty_months,
    inspector: form.inspector || null,
    remark: form.remark || null,
    plant_items: form.plant_items.map((item) => ({
      plant_name: item.plant_name,
      plant_category: item.plant_category,
      spec: item.spec || null,
      quantity: item.quantity,
      unit: item.unit,
    })),
  }
  try {
    if (isEdit.value) {
      await handoverAcceptanceApi.update(editingId.value, payload)
      ElMessage.success('移交验收单已更新')
    } else {
      await handoverAcceptanceApi.create(payload)
      ElMessage.success('移交验收单登记成功')
    }
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
.unit-suffix {
  margin-left: 8px;
  color: #909399;
}

.sub-table__add {
  margin-top: 8px;
}

.row-invalid :deep(.el-input__wrapper),
.row-invalid :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}

.row-error {
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.4;
  padding-top: 2px;
}
</style>
