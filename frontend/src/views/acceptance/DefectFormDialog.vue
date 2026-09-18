<template>
  <el-dialog :model-value="visible" title="追加缺陷" width="560px" destroy-on-close
             @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="缺陷描述" prop="description" :error="fieldErrors.description">
        <el-input v-model="form.description" type="textarea" :rows="2" maxlength="255"
                  placeholder="如：3 株樱花死亡、树穴覆盖物缺失" />
      </el-form-item>
      <el-form-item label="整改要求" :error="fieldErrors.requirement">
        <el-input v-model="form.requirement" maxlength="255"
                  placeholder="如：更换同规格苗木并加固支撑" />
      </el-form-item>
      <el-form-item label="完成期限" prop="deadline" :error="fieldErrors.deadline">
        <el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD"
                        placeholder="与移交方约定的完成期限" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'

const props = defineProps({
  acceptanceId: { type: Number, required: true },
})
const emit = defineEmits(['saved'])

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const fieldErrors = ref({})
const form = reactive({ description: '', requirement: '', deadline: '' })

const rules = {
  description: [{ required: true, message: '请输入缺陷描述', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择完成期限', trigger: 'change' }],
}

function open() {
  Object.assign(form, { description: '', requirement: '', deadline: '' })
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
  try {
    await handoverAcceptanceApi.addDefect(props.acceptanceId, {
      description: form.description,
      requirement: form.requirement || null,
      deadline: form.deadline,
    })
    ElMessage.success('缺陷已登记')
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
