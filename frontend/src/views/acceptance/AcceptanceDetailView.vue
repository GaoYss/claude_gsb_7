<template>
  <div class="page" v-loading="loading">
    <template v-if="detail">
      <PageHeader :title="`验收单 ${detail.acceptance_no}`"
                  :description="`${detail.green_space?.name || ''} · 移交方 ${detail.handover_party}`">
        <template #tag>
          <EnumTag group="acceptance_status" :value="detail.status" :label="detail.status_label" />
          <el-tag v-if="detail.is_warranty_expired && detail.status === 'passed'"
                  type="danger" size="small" effect="plain">质保期满</el-tag>
        </template>
        <template #actions>
          <el-button v-if="['pending', 'rectifying'].includes(detail.status)" type="primary"
                     :icon="'Stamp'" @click="acceptDialog.open(detail)">验收登记</el-button>
          <el-button v-if="detail.status !== 'closed'" :icon="'Plus'"
                     @click="defectForm.open()">追加缺陷</el-button>
          <el-button v-if="detail.status === 'passed'" type="success" :icon="'CircleCheck'"
                     @click="close">办结</el-button>
          <el-button v-if="detail.status !== 'closed'" :icon="'Edit'"
                     @click="formDialog.open(detail)">编辑</el-button>
          <el-button v-if="detail.status !== 'closed'" type="danger" plain :icon="'Delete'"
                     @click="remove">删除</el-button>
        </template>
      </PageHeader>

      <div class="panel">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="所属绿地">{{ detail.green_space?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="移交方">{{ detail.handover_party }}</el-descriptions-item>
          <el-descriptions-item label="接收单位">{{ detail.receiver || '-' }}</el-descriptions-item>
          <el-descriptions-item label="验收人">{{ detail.inspector || '-' }}</el-descriptions-item>
          <el-descriptions-item label="登记面积">{{ formatArea(detail.area_sqm) }}</el-descriptions-item>
          <el-descriptions-item label="实测面积">
            <span :class="{ 'area-diff': areaDiffers }">{{ formatArea(detail.measured_area_sqm) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="验收日期">{{ detail.acceptance_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="质保期">{{ detail.warranty_months }} 个月</el-descriptions-item>
          <el-descriptions-item label="质保截止">
            <span :class="{ 'warranty-expired': detail.is_warranty_expired }">
              {{ detail.warranty_end_date || '验收通过后起算' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="登记时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="panel">
        <div class="table-toolbar">
          <span class="panel-title">苗木清单核对</span>
          <span class="summary-text">
            共 {{ detail.plant_items.length }} 项，
            合格 {{ qualifiedCount }} 项，不合格 {{ unqualifiedCount }} 项
          </span>
        </div>
        <el-table :data="detail.plant_items" border stripe size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column label="苗木名称" min-width="140">
            <template #default="{ row }">
              <div>{{ row.plant_name }}</div>
              <EnumTag group="plant_category" :value="row.plant_category" :label="row.plant_category_label" />
            </template>
          </el-table-column>
          <el-table-column prop="spec" label="规格" width="140">
            <template #default="{ row }">{{ row.spec || '-' }}</template>
          </el-table-column>
          <el-table-column label="清单数量" width="110" align="right">
            <template #default="{ row }">{{ formatNumber(row.quantity) }} {{ row.unit_label }}</template>
          </el-table-column>
          <el-table-column label="实核数量" width="110" align="right">
            <template #default="{ row }">
              <span :class="{ 'quantity-diff': quantityDiffers(row) }">
                {{ row.checked_quantity === null ? '-' : `${formatNumber(row.checked_quantity)} ${row.unit_label}` }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="长势" width="110">
            <template #default="{ row }">
              <EnumTag v-if="row.growth_status" group="growth_status"
                       :value="row.growth_status" :label="row.growth_status_label" />
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="核对结论" width="100">
            <template #default="{ row }">
              <EnumTag group="item_check_result" :value="row.check_result" :label="row.check_result_label" />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="table-toolbar">
          <span class="panel-title">整改清单</span>
          <span class="summary-text">
            待整改 {{ detail.open_defect_count }} 项 / 共 {{ detail.defects.length }} 项
          </span>
        </div>
        <el-table :data="detail.defects" border stripe size="small" empty-text="暂无缺陷记录">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="description" label="缺陷描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="requirement" label="整改要求" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.requirement || '-' }}</template>
          </el-table-column>
          <el-table-column label="完成期限" width="110">
            <template #default="{ row }">
              <span :class="{ 'deadline-overdue': row.is_overdue }">{{ row.deadline }}</span>
              <el-tag v-if="row.is_overdue" type="danger" size="small" effect="plain">逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <EnumTag group="defect_status" :value="row.status" :label="row.status_label" />
            </template>
          </el-table-column>
          <el-table-column label="整改情况" min-width="170">
            <template #default="{ row }">
              <template v-if="row.status === 'done'">
                {{ row.finished_date }} {{ row.finished_note || '' }}
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'open' && detail.status !== 'closed'">
                <el-button link type="success" @click="defectComplete.open(row)">整改完成</el-button>
                <el-button link type="danger" @click="removeDefect(row)">删除</el-button>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="table-toolbar">
          <span class="panel-title">质保回访</span>
          <div>
            <span class="summary-text" style="margin-right: 12px">
              处理中 {{ detail.open_follow_up_count }} 条 / 共 {{ detail.follow_ups.length }} 条
            </span>
            <el-button v-if="detail.status === 'passed'" type="primary" plain size="small"
                       :icon="'Plus'" @click="followUpForm.open()">登记回访</el-button>
          </div>
        </div>
        <el-table :data="detail.follow_ups" border stripe size="small" empty-text="暂无回访记录">
          <el-table-column prop="visit_date" label="回访日期" width="105" />
          <el-table-column prop="issue" label="问题描述" min-width="220" show-overflow-tooltip />
          <el-table-column prop="handling" label="处理情况" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.handling || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <EnumTag group="follow_up_status" :value="row.status" :label="row.status_label" />
            </template>
          </el-table-column>
          <el-table-column prop="visitor" label="回访人" width="100">
            <template #default="{ row }">{{ row.visitor || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button v-if="detail.status !== 'closed'" link type="primary"
                         @click="followUpForm.open(row)">处理</el-button>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <AcceptDialog ref="acceptDialog" @saved="load" />
      <AcceptanceFormDialog ref="formDialog" @saved="load" />
      <DefectFormDialog ref="defectForm" :acceptance-id="detail.id" @saved="load" />
      <DefectCompleteDialog ref="defectComplete" :acceptance-id="detail.id" @saved="load" />
      <FollowUpFormDialog ref="followUpForm" :acceptance-id="detail.id" @saved="load" />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { formatArea, formatDateTime, formatNumber } from '@/utils/format'

import AcceptDialog from './AcceptDialog.vue'
import AcceptanceFormDialog from './AcceptanceFormDialog.vue'
import DefectCompleteDialog from './DefectCompleteDialog.vue'
import DefectFormDialog from './DefectFormDialog.vue'
import FollowUpFormDialog from './FollowUpFormDialog.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref(null)
const acceptDialog = ref(null)
const formDialog = ref(null)
const defectForm = ref(null)
const defectComplete = ref(null)
const followUpForm = ref(null)

const qualifiedCount = computed(
  () => (detail.value?.plant_items || []).filter((item) => item.check_result === 'qualified').length,
)
const unqualifiedCount = computed(
  () => (detail.value?.plant_items || []).filter((item) => item.check_result === 'unqualified').length,
)
const areaDiffers = computed(() => {
  if (!detail.value || detail.value.measured_area_sqm === null) return false
  return Math.abs(Number(detail.value.measured_area_sqm) - Number(detail.value.area_sqm)) > 0.01
})

function quantityDiffers(row) {
  if (row.checked_quantity === null || row.checked_quantity === undefined) return false
  return Math.abs(Number(row.checked_quantity) - Number(row.quantity)) > 0.01
}

async function load() {
  loading.value = true
  try {
    detail.value = await handoverAcceptanceApi.detail(route.params.id)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function close() {
  try {
    await ElMessageBox.confirm(
      '办结后验收单将转为「已办结」，质保责任终结且不可再修改，确认办结吗？',
      '办结确认',
      { type: 'warning', confirmButtonText: '办结', cancelButtonText: '取消' },
    )
    await handoverAcceptanceApi.close(detail.value.id)
    ElMessage.success('验收单已办结')
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

async function remove() {
  const doDelete = async (force) => {
    await handoverAcceptanceApi.remove(detail.value.id, force ? { force: 'true' } : undefined)
    ElMessage.success('移交验收单已删除')
    router.push({ name: 'acceptance-list' })
  }
  try {
    await ElMessageBox.confirm(`确认删除验收单「${detail.value.acceptance_no}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    try {
      await doDelete(false)
    } catch (error) {
      if (error?.status !== 409) return
      await ElMessageBox.confirm(error.message, '删除将级联清除关联数据', {
        type: 'warning',
        confirmButtonText: '仍要删除',
        cancelButtonText: '取消',
      })
      await doDelete(true)
    }
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

async function removeDefect(row) {
  try {
    await ElMessageBox.confirm(`确认删除缺陷「${row.description}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await handoverAcceptanceApi.removeDefect(detail.value.id, row.id)
    ElMessage.success('缺陷已删除')
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

onMounted(load)
</script>

<style scoped>
.panel-title {
  font-weight: 600;
}

.area-diff,
.quantity-diff,
.deadline-overdue,
.warranty-expired {
  color: #f56c6c;
  font-weight: 600;
}
</style>
