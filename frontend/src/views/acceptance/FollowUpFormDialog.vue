<template>
  <el-dialog :model-value="visible" :title="isEdit ? '处理回访问题' : '登记质保回访'"
             width="560px" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="回访日期" prop="visit_date" :error="fieldErrors.visit_date">
        <el-date-picker v-model="form.visit_date" type="date" value-format="YYYY-MM-DD"
                        placeholder="回访日期" style="width: 100%" />
      </el-form-item>
      <el-form-item label="问题描述" prop="issue" :error="fieldErrors.issue">
        <el-input v-model="form.issue" type="textarea" :rows="2" maxlength="255"
                  placeholder="质保期内发现的问题" />
      </el-form-item>
      <el-form-item label="处理情况" :error="fieldErrors.handling">
        <el-input v-model="form.handling" type="textarea" :rows="2" maxlength="255"
                  placeholder="移交方处理措施与复查结果" />
      </el-form-item>
      <el-form-item label="处理状态" :error="fieldErrors.status">
        <el-radio-group v-model="form.status">
          <el-radio-button v-for="item in statusOptions" :key="item.value"
                           :value="item.value">{{ item.label }}</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="回访人" :error="fieldErrors.visitor">
        <el-input v-model="form.visitor" maxlength="64" />
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
import { useEnumOptions } from '@/composables/useEnumOptions'
import { today } from '@/utils/format'

const props = defineProps({
  acceptanceId: { type: Number, required: true },
})
const emit = defineEmits(['saved'])

const { options: statusOptions } = useEnumOptions('follow_up_status')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const fieldErrors = ref({})
const form = reactive({ visit_date: '', issue: '', handling: '', status: 'open', visitor: '' })

const isEdit = computed(() => editingId.value !== null)

const rules = {
  visit_date: [{ required: true, message: '请选择回访日期', trigger: 'change' }],
  issue: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
}

function open(row = null) {
  editingId.value = row?.id ?? null
  Object.assign(form, {
    visit_date: row?.visit_date || today(),
    issue: row?.issue || '',
    handling: row?.handling || '',
    status: row?.status || 'open',
    visitor: row?.visitor || '',
  })
  fieldErrors.value = {}
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
    issue: form.issue,
    handling: form.handling || null,
    status: form.status,
    visitor: form.visitor || null,
  }
  try {
    if (isEdit.value) {
      await handoverAcceptanceApi.updateFollowUp(props.acceptanceId, editingId.value, payload)
      ElMessage.success('回访记录已更新')
    } else {
      await handoverAcceptanceApi.addFollowUp(props.acceptanceId, payload)
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
