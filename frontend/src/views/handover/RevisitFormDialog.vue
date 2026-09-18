<template>
  <el-dialog :model-value="visible"
             :title="isEdit ? '编辑质保回访记录' : '登记质保回访'"
             width="600px" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="回访日期" prop="visit_date" :error="fieldErrors.visit_date">
            <el-date-picker v-model="form.visit_date" type="date" value-format="YYYY-MM-DD"
                            style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="回访人" :error="fieldErrors.visitor">
            <el-input v-model="form.visitor" maxlength="64" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="成活率" :error="fieldErrors.survival_rate">
            <el-input-number v-model="form.survival_rate" :min="0" :max="100" :precision="1"
                             :controls="false" placeholder="0-100" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="回访结果" prop="result">
            <el-radio-group v-model="form.result">
              <el-radio value="normal">正常</el-radio>
              <el-radio value="abnormal">异常</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="发现问题" :error="fieldErrors.issue">
            <el-input v-model="form.issue" type="textarea" :rows="2" maxlength="1000"
                      :placeholder="form.result === 'abnormal' ? '回访发现异常时必须填写' : '无问题可留空'" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="处理情况" :error="fieldErrors.handling">
            <el-input v-model="form.handling" type="textarea" :rows="2" maxlength="1000" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="下次回访" :error="fieldErrors.next_visit_date">
            <el-date-picker v-model="form.next_visit_date" type="date" value-format="YYYY-MM-DD"
                            style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="备注" :error="fieldErrors.remark">
            <el-input v-model="form.remark" type="textarea" :rows="1" maxlength="500" />
          </el-form-item>
        </el-col>
      </el-row>
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
import { today } from '@/utils/format'

const emit = defineEmits(['saved'])

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const handoverId = ref(null)
const editingId = ref(null)
const fieldErrors = ref({})
const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value !== null)

const rules = {
  visit_date: [{ required: true, message: '请选择回访日期', trigger: 'change' }],
}

function emptyForm() {
  return {
    visit_date: today(),
    visitor: '',
    survival_rate: null,
    result: 'normal',
    issue: '',
    handling: '',
    next_visit_date: '',
    remark: '',
  }
}

function open(handover, row = null) {
  handoverId.value = handover
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  editingId.value = row?.id ?? null
  if (row) {
    Object.keys(form).forEach((key) => {
      if (row[key] !== undefined && row[key] !== null) form[key] = row[key]
    })
    if (!form.next_visit_date) form.next_visit_date = ''
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
    visit_date: form.visit_date,
    visitor: form.visitor || null,
    survival_rate: form.survival_rate,
    issue: form.issue || null,
    handling: form.handling || null,
    result: form.result,
    next_visit_date: form.next_visit_date || null,
    remark: form.remark || null,
  }
  try {
    if (isEdit.value) {
      await handoverAcceptanceApi.updateRevisit(handoverId.value, editingId.value, payload)
      ElMessage.success('回访记录已更新')
    } else {
      await handoverAcceptanceApi.createRevisit(handoverId.value, payload)
      ElMessage.success('回访记录已登记')
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
