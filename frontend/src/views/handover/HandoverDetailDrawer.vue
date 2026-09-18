<template>
  <el-drawer :model-value="visible" size="760px"
             :title="detail.handover_no ? `移交验收单 · ${detail.handover_no}` : '移交验收单详情'"
             @update:model-value="close">
    <div v-loading="loading" class="drawer-body">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="验收单状态">
          <EnumTag group="handover_status" :value="detail.status" :label="detail.status_label" />
        </el-descriptions-item>
        <el-descriptions-item label="移交日期">{{ formatDate(detail.handover_date) }}</el-descriptions-item>
        <el-descriptions-item label="所属绿地" :span="2">
          {{ detail.green_space ? `${detail.green_space.code} ${detail.green_space.name}` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="移交单位">{{ detail.transferor }}</el-descriptions-item>
        <el-descriptions-item label="接管单位">{{ detail.receiver || '-' }}</el-descriptions-item>
        <el-descriptions-item label="登记面积">{{ formatArea(detail.area_sqm) }}</el-descriptions-item>
        <el-descriptions-item label="实测面积">
          <span :class="{ 'area-missing': detail.checked_area_sqm === null }">
            {{ formatArea(detail.checked_area_sqm) }}
          </span>
          <span v-if="areaDiff !== null" :class="diffClass" class="area-diff">
            {{ areaDiff > 0 ? '+' : '' }}{{ areaDiff }}%
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="验收日期">{{ formatDate(detail.acceptance_date) }}</el-descriptions-item>
        <el-descriptions-item label="验收人">{{ detail.inspector || '-' }}</el-descriptions-item>
        <el-descriptions-item label="质保期">
          {{ detail.warranty_months }} 个月
        </el-descriptions-item>
        <el-descriptions-item label="质保区间">
          <template v-if="detail.warranty_start_date">
            {{ formatDate(detail.warranty_start_date) }} 至 {{ formatDate(detail.warranty_end_date) }}
            <el-tag v-if="progress.warranty_days_remaining !== null" size="small" effect="plain"
                    :type="progress.warranty_days_remaining <= 30 ? 'warning' : 'success'">
              {{ progress.warranty_days_remaining > 0
                  ? `剩余 ${progress.warranty_days_remaining} 天` : '已到期' }}
            </el-tag>
          </template>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.conclusion" label="验收意见" :span="2">
          {{ detail.conclusion }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.remark" label="备注" :span="2">{{ detail.remark }}</el-descriptions-item>
      </el-descriptions>

      <div class="stat-grid drawer-stats">
        <StatCard label="苗木核对" :value="`${progress.checked_count ?? 0}/${progress.item_count ?? 0}`"
                  :hint="`不符 ${progress.deficient_count ?? 0} 项`" />
        <StatCard label="待整改缺陷" :value="progress.open_defect_count ?? 0" unit="项"
                  :hint="`超期 ${progress.overdue_defect_count ?? 0} 项`"
                  :tone="(progress.overdue_defect_count ?? 0) ? 'danger' : 'default'" />
        <StatCard label="质保回访" :value="progress.revisit_count ?? 0" unit="次"
                  :hint="progress.last_visit_date ? `最近 ${progress.last_visit_date}` : '暂无回访'" />
      </div>

      <div class="table-toolbar">
        <span class="panel-title">苗木清单核对</span>
      </div>
      <el-table :data="detail.plant_items || []" size="small" border
                :row-class-name="plantRowClass" empty-text="暂无苗木清单">
        <el-table-column prop="plant_name" label="苗木名称" min-width="120">
          <template #default="{ row }">
            <div>{{ row.plant_name }}</div>
            <div class="cell-sub">{{ row.plant_category_label }} · {{ row.spec || '无规格' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="登记数量" width="110" align="right">
          <template #default="{ row }">{{ formatNumber(row.quantity) }} {{ row.unit_label }}</template>
        </el-table-column>
        <el-table-column label="核对数量" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.checked_quantity !== null">
              {{ formatNumber(row.checked_quantity) }} {{ row.unit_label }}
            </span>
            <span v-else class="text-muted">未核对</span>
          </template>
        </el-table-column>
        <el-table-column label="长势" width="80">
          <template #default="{ row }">
            <EnumTag v-if="row.growth_condition" group="growth_condition"
                     :value="row.growth_condition" :label="row.growth_condition_label" />
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="结论" width="80">
          <template #default="{ row }">
            <EnumTag v-if="row.check_result" group="plant_check_result"
                     :value="row.check_result" :label="row.check_result_label" />
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-toolbar">
        <span class="panel-title">缺陷整改清单</span>
        <el-button v-if="detail.status === 'rectifying'" link type="primary" :icon="'Plus'"
                   @click="addDefect">补登缺陷</el-button>
      </div>
      <el-table :data="detail.defects || []" size="small" border empty-text="暂无缺陷记录">
        <el-table-column prop="description" label="缺陷描述" min-width="170" show-overflow-tooltip />
        <el-table-column prop="location" label="位置" width="100">
          <template #default="{ row }">{{ row.location || '-' }}</template>
        </el-table-column>
        <el-table-column label="程度" width="74">
          <template #default="{ row }">
            <EnumTag group="defect_severity" :value="row.severity" :label="row.severity_label" />
          </template>
        </el-table-column>
        <el-table-column label="整改期限" width="130">
          <template #default="{ row }">
            {{ formatDate(row.deadline) }}
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="plain">超期</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="112">
          <template #default="{ row }">
            <EnumTag group="defect_status" :value="row.status" :label="row.status_label" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <template v-if="detail.status === 'rectifying'">
              <el-button v-if="row.status !== 'closed'" link type="primary"
                         @click="editDefect(row)">处理</el-button>
              <el-button v-if="row.status === 'pending'" link type="danger"
                         @click="removeDefect(row)">删除</el-button>
              <span v-if="row.status === 'closed'" class="text-muted">已闭环</span>
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-toolbar">
        <span class="panel-title">质保期回访记录</span>
        <el-button v-if="detail.status === 'accepted'" link type="primary" :icon="'Plus'"
                   @click="addRevisit">登记回访</el-button>
      </div>
      <el-table :data="detail.revisits || []" size="small" border empty-text="暂无回访记录">
        <el-table-column prop="visit_date" label="回访日期" width="105" />
        <el-table-column prop="visitor" label="回访人" width="80">
          <template #default="{ row }">{{ row.visitor || '-' }}</template>
        </el-table-column>
        <el-table-column label="成活率" width="84">
          <template #default="{ row }">{{ row.survival_rate !== null ? `${row.survival_rate}%` : '-' }}</template>
        </el-table-column>
        <el-table-column label="结果" width="74">
          <template #default="{ row }">
            <EnumTag group="revisit_result" :value="row.result" :label="row.result_label" />
          </template>
        </el-table-column>
        <el-table-column prop="issue" label="发现问题 / 处理" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.issue || '无异常' }}</div>
            <div v-if="row.handling" class="cell-sub">处理：{{ row.handling }}</div>
          </template>
        </el-table-column>
        <el-table-column label="下次回访" width="105">
          <template #default="{ row }">{{ formatDate(row.next_visit_date) }}</template>
        </el-table-column>
        <el-table-column v-if="detail.status === 'accepted'" label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="editRevisit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRevisit(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="close">关闭</el-button>
      <el-button v-if="detail.status === 'pending' || detail.status === 'rejected'" type="primary"
                 @click="acceptDialog.open(detail.id)">执行验收</el-button>
      <el-button v-if="detail.status === 'rectifying'" type="success"
                 @click="complete">复验闭环</el-button>
    </template>

    <AcceptanceDialog ref="acceptDialog" @saved="reload" />
    <DefectEditDialog ref="defectDialog" @saved="reload" />
    <RevisitFormDialog ref="revisitDialog" @saved="reload" />
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import StatCard from '@/components/common/StatCard.vue'
import { formatArea, formatDate, formatNumber } from '@/utils/format'

import AcceptanceDialog from './AcceptanceDialog.vue'
import DefectEditDialog from './DefectEditDialog.vue'
import RevisitFormDialog from './RevisitFormDialog.vue'

const emit = defineEmits(['updated'])

const visible = ref(false)
const loading = ref(false)
const detail = ref({})
const currentId = ref(null)
const acceptDialog = ref(null)
const defectDialog = ref(null)
const revisitDialog = ref(null)

const progress = computed(() => detail.value.progress || {})

const areaDiff = computed(() => {
  const registered = Number(detail.value.area_sqm)
  const checked = Number(detail.value.checked_area_sqm)
  if (!registered || checked === null || Number.isNaN(checked)) return null
  return Math.round(((checked - registered) / registered) * 1000) / 10
})
const diffClass = computed(() => (Math.abs(areaDiff.value ?? 0) > 2 ? 'area-diff--warn' : 'area-diff--ok'))

function plantRowClass({ row }) {
  return row.check_result === 'deficient' ? 'row-deficient' : ''
}

async function open(id) {
  currentId.value = id
  visible.value = true
  await load()
}

async function load() {
  if (!currentId.value) return
  loading.value = true
  try {
    detail.value = await handoverAcceptanceApi.detail(currentId.value)
  } finally {
    loading.value = false
  }
}

async function reload() {
  await load()
  emit('updated')
}

function close() {
  visible.value = false
}

async function complete() {
  const openCount = progress.value.open_defect_count ?? 0
  try {
    await ElMessageBox.confirm(
      openCount
        ? `仍有 ${openCount} 项缺陷未完成复验闭环，确认提交将被后端拒绝。`
        : '全部缺陷已完成整改复验，确认闭环并通过验收？',
      '复验闭环',
      { type: 'warning', confirmButtonText: '确认闭环', cancelButtonText: '取消' },
    )
    await handoverAcceptanceApi.complete(currentId.value, {})
    ElMessage.success('缺陷已全部闭环，验收通过')
    await reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

function addDefect() {
  defectDialog.value?.open(currentId.value)
}

function editDefect(row) {
  defectDialog.value?.open(currentId.value, row)
}

async function removeDefect(row) {
  try {
    await ElMessageBox.confirm(`确认删除缺陷「${row.description}」吗？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await handoverAcceptanceApi.removeDefect(currentId.value, row.id)
    ElMessage.success('缺陷已删除')
    await reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

function addRevisit() {
  revisitDialog.value?.open(currentId.value)
}

function editRevisit(row) {
  revisitDialog.value?.open(currentId.value, row)
}

async function removeRevisit(row) {
  try {
    await ElMessageBox.confirm('确认删除该条回访记录吗？', '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await handoverAcceptanceApi.removeRevisit(currentId.value, row.id)
    ElMessage.success('回访记录已删除')
    await reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

defineExpose({ open })
</script>

<style scoped>
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-stats {
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
}

.panel-title {
  font-weight: 600;
}

.cell-sub {
  color: #909399;
  font-size: 12px;
}

.text-muted {
  color: #c0c4cc;
}

.area-missing {
  color: #c0c4cc;
}

.area-diff {
  margin-left: 8px;
  font-size: 12px;
}

.area-diff--ok {
  color: var(--el-color-success);
}

.area-diff--warn {
  color: var(--el-color-warning);
}

:deep(.row-deficient) {
  background-color: #fef0f0;
}
</style>
