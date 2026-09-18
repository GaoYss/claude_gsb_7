<template>
  <el-dialog :model-value="visible"
             :title="isCreate ? '补登缺陷' : '缺陷整改处理'"
             width="560px" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="缺陷描述" prop="description" :error="fieldErrors.description">
        <el-input v-model="form.description" type="textarea" :rows="2" maxlength="500"
                  :disabled="readonly" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="位置" :error="fieldErrors.location">
            <el-input v-model="form.location" maxlength="128" :disabled="readonly" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="严重程度" :error="fieldErrors.severity">
            <el-select v-model="form.severity" style="width: 100%" :disabled="readonly">
              <el-option v-for="item in severityOptions" :key="item.value"
                         :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="整改期限" prop="deadline" :error="fieldErrors.deadline">
            <el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD"
                            style="width: 100%" :disabled="readonly" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="责任单位" :error="fieldErrors.responsible">
            <el-input v-model="form.responsible" maxlength="96" :disabled="readonly" />
          </el-form-item>
        </el-col>
        <el-col v-if="!isCreate" :span="24">
          <el-form-item label="当前状态">
            <EnumTag group="defect_status" :value="form.status" />
            <span v-if="form.rectified_at" class="status-time">
              整改完成 {{ formatDateTime(form.rectified_at) }}
            </span>
          </el-form-item>
        </el-col>
        <el-col v-if="!isCreate" :span="24">
          <el-form-item label="复验情况" :error="fieldErrors.recheck_note">
            <el-input v-model="form.recheck_note" type="textarea" :rows="2" maxlength="1000"
                      :disabled="readonly || form.status === 'pending'"
                      placeholder="复验通过闭环前必须填写" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="备注" :error="fieldErrors.remark">
            <el-input v-model="form.remark" type="textarea" :rows="1" maxlength="500"
                      :disabled="readonly" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <template #footer>
      <el-button @click="close">关闭</el-button>
      <template v-if="isCreate">
        <el-button type="primary" :loading="submitting" @click="create">登记缺陷</el-button>
      </template>
      <template v-else-if="!readonly">
        <el-button :loading="submitting" @click="submit(form.status)">保存</el-button>
        <el-button v-if="form.status === 'pending'" type="warning" :loading="submitting"
                   @click="submit('rectified')">标记已整改</el-button>
        <el-button v-if="form.status === 'rectified'" type="success" :loading="submitting"
                   @click="submit('closed')">复验通过闭环</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { formatDateTime, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: severityOptions } = useEnumOptions('defect_severity')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const handoverId = ref(null)
const editingId = ref(null)
const fieldErrors = ref({})
const form = reactive(emptyForm())

const isCreate = computed(() => editingId.value === null)
const readonly = computed(() => !isCreate.value && form.status === 'closed')

const rules = {
  description: [{ required: true, message: '请填写缺陷描述', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择整改期限', trigger: 'change' }],
}

function emptyForm() {
  return {
    description: '', location: '', severity: 'general', deadline: today(),
    responsible: '', status: 'pending', recheck_note: '', remark: '',
    rectified_at: null,
  }
}

function open(handover, defect = null) {
  handoverId.value = handover
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  editingId.value = defect?.id ?? null
  if (defect) {
    Object.assign(form, {
      description: defect.description,
      location: defect.location || '',
      severity: defect.severity,
      deadline: defect.deadline,
      responsible: defect.responsible || '',
      status: defect.status,
      recheck_note: defect.recheck_note || '',
      remark: defect.remark || '',
      rectified_at: defect.rectified_at,
    })
  }
  visible.value = true
}

function close() {
  visible.value = false
}

function buildPayload(status) {
  return {
    description: form.description,
    location: form.location || null,
    severity: form.severity,
    deadline: form.deadline,
    responsible: form.responsible || null,
    remark: form.remark || null,
    ...(status ? { status } : {}),
    ...(editingId.value ? { recheck_note: form.recheck_note || null } : {}),
  }
}

async function create() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  fieldErrors.value = {}
  try {
    await handoverAcceptanceApi.createDefect(handoverId.value, buildPayload())
    ElMessage.success('缺陷已登记')
    emit('saved')
    close()
  } catch (error) {
    fieldErrors.value = error?.details || {}
  } finally {
    submitting.value = false
  }
}

async function submit(status) {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  fieldErrors.value = {}
  try {
    await handoverAcceptanceApi.updateDefect(handoverId.value, editingId.value, buildPayload(status))
    ElMessage.success(status === 'closed' ? '缺陷已复验闭环' : '缺陷整改情况已更新')
    emit('saved')
    close()
  } catch (error) {
    fieldErrors.value = error?.details || {}
    ElMessage.error(error?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.status-time {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
