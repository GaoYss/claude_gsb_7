<template>
  <el-dialog :model-value="visible" title="标记整改完成" width="560px" destroy-on-close
             @update:model-value="close">
    <el-alert v-if="defect" type="warning" :closable="false" class="defect-tip">
      {{ defect.description }}
    </el-alert>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="完成日期" prop="finished_date" :error="fieldErrors.finished_date">
        <el-date-picker v-model="form.finished_date" type="date" value-format="YYYY-MM-DD"
                        placeholder="整改完成日期" style="width: 100%" />
      </el-form-item>
      <el-form-item label="复核说明" :error="fieldErrors.finished_note">
        <el-input v-model="form.finished_note" type="textarea" :rows="2" maxlength="255"
                  placeholder="如：已更换同规格苗木 3 株，现场复核合格" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">确认完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import { today } from '@/utils/format'

const props = defineProps({
  acceptanceId: { type: Number, required: true },
})
const emit = defineEmits(['saved'])

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const defect = ref(null)
const fieldErrors = ref({})
const form = reactive({ finished_date: '', finished_note: '' })

const rules = {
  finished_date: [{ required: true, message: '请选择完成日期', trigger: 'change' }],
}

function open(row) {
  defect.value = row
  Object.assign(form, { finished_date: today(), finished_note: '' })
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
    await handoverAcceptanceApi.completeDefect(props.acceptanceId, defect.value.id, {
      finished_date: form.finished_date,
      finished_note: form.finished_note || null,
    })
    ElMessage.success('缺陷已标记整改完成')
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
.defect-tip {
  margin-bottom: 16px;
}
</style>
