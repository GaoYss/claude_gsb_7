<template>
  <el-dialog :model-value="visible"
             :title="isEdit ? `编辑验收单 · ${form.acceptance_no}` : '登记移交验收单'"
             width="860px" top="5vh" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="所属绿地" prop="green_space_id" :error="fieldErrors.green_space_id">
        <GreenSpaceSelect v-model="form.green_space_id" :preset="spacePreset" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="移交方" prop="handover_party" :error="fieldErrors.handover_party">
            <el-input v-model="form.handover_party" placeholder="如：市政园林工程公司" maxlength="128" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="接收单位" :error="fieldErrors.receiver">
            <el-input v-model="form.receiver" placeholder="如：区绿化养护管理所" maxlength="128" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="绿化面积（㎡）" prop="area_sqm" :error="fieldErrors.area_sqm">
            <el-input-number v-model="form.area_sqm" :min="0.01" :max="99999999" :precision="2"
                             :controls="false" placeholder="移交登记的绿化面积" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="质保期（月）" prop="warranty_months" :error="fieldErrors.warranty_months">
            <el-input-number v-model="form.warranty_months" :min="1" :max="120" :precision="0"
                             :controls="false" placeholder="如：12 / 24" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="验收人" :error="fieldErrors.inspector">
            <el-input v-model="form.inspector" maxlength="64" placeholder="可验收登记时再填" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="苗木清单">
        <div class="plant-list">
          <div class="plant-list__head">
            <span>苗木名称</span><span>类别</span><span>规格</span><span>数量</span><span>单位</span><span />
          </div>
          <div v-for="(row, index) in form.plants" :key="index" class="plant-list__row">
            <el-input v-model="row.plant_name" placeholder="如：香樟" maxlength="96"
                      :disabled="plantsLocked" />
            <el-select v-model="row.plant_category" :disabled="plantsLocked">
              <el-option v-for="item in categoryOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
            <el-input v-model="row.spec" placeholder="如：胸径 15cm" maxlength="64"
                      :disabled="plantsLocked" />
            <el-input-number v-model="row.quantity" :min="0.01" :max="9999999" :precision="2"
                             :controls="false" placeholder="数量" :disabled="plantsLocked" />
            <el-select v-model="row.unit" :disabled="plantsLocked">
              <el-option v-for="item in unitOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
            <el-button link type="danger" :icon="'Delete'" :disabled="plantsLocked"
                       @click="removePlant(index)" />
          </div>
          <div class="plant-list__footer">
            <el-button v-if="!plantsLocked" link type="primary" :icon="'Plus'" @click="addPlant">
              添加苗木
            </el-button>
            <span v-if="plantsLocked" class="plant-list__lock-hint">
              验收单已进入验收流程，苗木清单不可再调整
            </span>
          </div>
          <div v-if="plantErrors.length" class="plant-list__errors">
            <div v-for="(message, key) in plantErrors" :key="key">{{ message }}</div>
          </div>
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

const emit = defineEmits(['saved'])

const { options: categoryOptions } = useEnumOptions('plant_category')
const { options: unitOptions } = useEnumOptions('measure_unit')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const editingStatus = ref('pending')
const fieldErrors = ref({})
const spacePreset = ref(null)
const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value !== null)
const plantsLocked = computed(() => isEdit.value && editingStatus.value !== 'pending')

const plantErrors = computed(() => {
  const entries = Object.entries(fieldErrors.value || {})
    .filter(([key]) => key.startsWith('plants.'))
  const messages = {}
  entries.forEach(([key, message]) => {
    const rowNo = Number(key.split('.')[1]) + 1
    messages[key] = `第 ${rowNo} 行：${message}`
  })
  return messages
})

const rules = {
  green_space_id: [{ required: true, message: '请选择所属绿地', trigger: 'change' }],
  handover_party: [{ required: true, message: '请输入移交方', trigger: 'blur' }],
  area_sqm: [{ required: true, message: '请输入绿化面积', trigger: 'blur' }],
  warranty_months: [{ required: true, message: '请输入质保期（月）', trigger: 'blur' }],
}

function emptyPlant() {
  return { plant_name: '', plant_category: 'tree', spec: '', quantity: null, unit: 'plant' }
}

function emptyForm() {
  return {
    acceptance_no: '',
    green_space_id: null,
    handover_party: '',
    receiver: '',
    area_sqm: null,
    warranty_months: 12,
    inspector: '',
    remark: '',
    plants: [emptyPlant()],
  }
}

function addPlant() {
  form.plants.push(emptyPlant())
}

function removePlant(index) {
  form.plants.splice(index, 1)
  if (!form.plants.length) addPlant()
}

async function open(row = null) {
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  spacePreset.value = null
  editingId.value = row?.id ?? null
  editingStatus.value = row?.status ?? 'pending'
  if (row) {
    ;['acceptance_no', 'green_space_id', 'handover_party', 'receiver', 'area_sqm',
      'warranty_months', 'inspector', 'remark'].forEach((key) => {
      if (row[key] !== undefined && row[key] !== null) form[key] = row[key]
    })
    spacePreset.value = row.green_space || null
    try {
      const detail = await handoverAcceptanceApi.detail(row.id)
      const items = detail?.plant_items || []
      form.plants = items.length
        ? items.map((item) => ({
            plant_name: item.plant_name,
            plant_category: item.plant_category,
            spec: item.spec || '',
            quantity: item.quantity,
            unit: item.unit,
          }))
        : [emptyPlant()]
    } catch {
      form.plants = [emptyPlant()]
    }
  }
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
    green_space_id: form.green_space_id,
    handover_party: form.handover_party,
    receiver: form.receiver || null,
    area_sqm: form.area_sqm,
    warranty_months: form.warranty_months,
    inspector: form.inspector || null,
    remark: form.remark || null,
  }
  if (!plantsLocked.value) {
    payload.plants = form.plants
      .filter((row) => row.plant_name && row.plant_name.trim())
      .map((row) => ({
        plant_name: row.plant_name.trim(),
        plant_category: row.plant_category,
        spec: row.spec || null,
        quantity: row.quantity,
        unit: row.unit,
      }))
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
.plant-list {
  width: 100%;
  border: 1px solid var(--gs-border);
  border-radius: 6px;
  padding: 8px 12px;
}

.plant-list__head,
.plant-list__row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1.2fr 0.9fr 0.9fr 32px;
  gap: 8px;
  align-items: center;
}

.plant-list__head {
  color: #909399;
  font-size: 12px;
  padding: 2px 0 6px;
}

.plant-list__row {
  margin-bottom: 8px;
}

.plant-list__footer {
  display: flex;
  align-items: center;
  min-height: 24px;
}

.plant-list__lock-hint {
  color: #e6a23c;
  font-size: 12px;
}

.plant-list__errors {
  margin-top: 6px;
  color: #f56c6c;
  font-size: 12px;
  line-height: 1.6;
}
</style>
