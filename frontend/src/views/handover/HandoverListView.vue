<template>
  <div class="page">
    <PageHeader title="绿地移交验收" description="登记新建绿地移交信息，逐项核对面积/数量/长势，跟踪缺陷整改与质保期回访">
      <template #actions>
        <el-button type="primary" :icon="'Plus'" @click="formDialog.open(null, presetSpace)">登记移交单</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <div class="filter-bar">
        <el-input v-model="filters.keyword" placeholder="编号 / 移交单位 / 验收人" clearable
                  :prefix-icon="'Search'" @keyup.enter="search" @clear="search" />
        <div style="width: 220px">
          <GreenSpaceSelect v-model="filters.green_space_id" placeholder="按绿地筛选"
                            @update:model-value="search" />
        </div>
        <el-select v-model="filters.status" placeholder="验收状态" clearable @change="search">
          <el-option v-for="item in statusOptions" :key="item.value"
                     :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.warranty_state" placeholder="质保状态" clearable @change="search">
          <el-option label="质保在保" value="active" />
          <el-option label="30 天内到期" value="expiring" />
          <el-option label="已过质保期" value="expired" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" unlink-panels value-format="YYYY-MM-DD"
                        start-placeholder="移交日期起" end-placeholder="移交日期止" @change="onDateChange" />
        <el-checkbox v-model="overdueOnly" border @change="onOverdueChange">仅看超期缺陷</el-checkbox>
        <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
        <el-button :icon="'RefreshLeft'" @click="reset">重置</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <StatCard label="待验收" :value="statusCount('pending')" unit="张"
                hint="尚未组织现场验收" icon="Document" />
      <StatCard label="整改中" :value="statusCount('rectifying')" unit="张"
                :hint="`超期缺陷 ${summary?.overdue_defect_count ?? 0} 项`"
                :tone="(summary?.overdue_defect_count ?? 0) ? 'danger' : 'warning'" icon="Tools" />
      <StatCard label="验收通过" :value="statusCount('accepted')" unit="张"
                hint="质保期内持续回访" tone="info" icon="CircleCheck" />
      <StatCard label="30 天内质保到期" :value="summary?.warranty_expiring_count ?? 0" unit="张"
                hint="及时安排质保到期前回访" tone="warning" icon="AlarmClock" />
    </div>

    <div class="panel">
      <div class="table-toolbar">
        <span class="summary-text">
          共 <strong>{{ meta.total }}</strong> 张验收单，
          登记面积合计 <strong>{{ formatArea(summary?.total_area ?? 0) }}</strong>，
          实测面积合计 <strong>{{ formatArea(summary?.total_checked_area ?? 0) }}</strong>
        </span>
        <el-button :icon="'Refresh'" text @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column label="验收单编号" min-width="165">
          <template #default="{ row }">
            <div class="cell-main">{{ row.handover_no }}</div>
            <div class="cell-sub">{{ row.transferor }}</div>
          </template>
        </el-table-column>
        <el-table-column label="所属绿地" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.green_space?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="handover_date" label="移交日期" width="105" />
        <el-table-column label="登记 / 实测面积" width="150" align="right">
          <template #default="{ row }">
            <div>{{ formatArea(row.area_sqm) }}</div>
            <div :class="row.checked_area_sqm === null ? 'cell-sub' : 'area-checked'">
              {{ formatArea(row.checked_area_sqm) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="质保期" width="135">
          <template #default="{ row }">
            <div>{{ row.warranty_months }} 个月</div>
            <div :class="warrantyTone(row)">
              {{ row.warranty_end_date ? `至 ${row.warranty_end_date}` : '未起算' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="缺陷整改" width="120">
          <template #default="{ row }">
            <span v-if="!row.progress || row.progress.defect_count === 0" class="text-muted">-</span>
            <template v-else>
              <el-tag :type="row.progress.open_defect_count ? 'danger' : 'success'" size="small">
                {{ row.progress.defect_count - row.progress.open_defect_count }}/{{ row.progress.defect_count }}
              </el-tag>
              <el-tag v-if="row.progress.overdue_defect_count" type="danger" size="small" effect="plain">
                超期 {{ row.progress.overdue_defect_count }}
              </el-tag>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="回访" width="64" align="center">
          <template #default="{ row }">{{ row.progress?.revisit_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="状态" width="98">
          <template #default="{ row }">
            <EnumTag group="handover_status" :value="row.status" :label="row.status_label" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="drawer.open(row.id)">详情</el-button>
            <el-button v-if="row.status === 'pending' || row.status === 'rejected'" link type="primary"
                       @click="formDialog.open(row)">编辑</el-button>
            <el-button v-if="row.status === 'pending' || row.status === 'rejected'" link type="success"
                       @click="acceptDialog.open(row.id)">验收</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="meta.total"
        :current-page="meta.page"
        :page-size="meta.page_size"
        :page-sizes="[10, 20, 50]"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <HandoverFormDialog ref="formDialog" @saved="load" />
    <AcceptanceDialog ref="acceptDialog" @saved="load" />
    <HandoverDetailDrawer ref="drawer" @updated="load" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { greenSpaceApi, handoverAcceptanceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import GreenSpaceSelect from '@/components/common/GreenSpaceSelect.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { useListQuery } from '@/composables/useListQuery'
import { formatArea } from '@/utils/format'

import AcceptanceDialog from './AcceptanceDialog.vue'
import HandoverDetailDrawer from './HandoverDetailDrawer.vue'
import HandoverFormDialog from './HandoverFormDialog.vue'

const route = useRoute()
const formDialog = ref(null)
const acceptDialog = ref(null)
const drawer = ref(null)
const dateRange = ref([])
const overdueOnly = ref(false)
const presetSpace = ref(null)

const { options: statusOptions } = useEnumOptions('handover_status')

const { filters, meta, items, summary, loading, load, search, resetFilters,
        handlePageChange, handleSizeChange } =
  useListQuery(handoverAcceptanceApi.list, {
    initialFilters: {
      keyword: '',
      green_space_id: route.query.green_space_id ? Number(route.query.green_space_id) : null,
      status: '',
      warranty_state: '',
      date_from: '',
      date_to: '',
      overdue_defects: false,
    },
  })

function statusCount(status) {
  return summary.value?.by_status?.[status] ?? 0
}

function warrantyTone(row) {
  if (!row.warranty_end_date || row.status !== 'accepted') return 'cell-sub'
  const days = Math.ceil((new Date(row.warranty_end_date) - new Date()) / 86400000)
  return days <= 30 ? 'warranty-expiring' : 'cell-sub'
}

function onDateChange(value) {
  filters.date_from = value?.[0] || ''
  filters.date_to = value?.[1] || ''
  search()
}

function onOverdueChange(checked) {
  filters.overdue_defects = checked
  search()
}

function reset() {
  dateRange.value = []
  overdueOnly.value = false
  resetFilters()
}

async function remove(row) {
  const needsForce = row.status === 'rectifying'
  try {
    await ElMessageBox.confirm(
      `确认删除移交验收单「${row.handover_no}」吗？${needsForce ? '该单已有缺陷记录，删除将一并清除。' : ''}`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await handoverAcceptanceApi.remove(row.id, needsForce ? { force: true } : {})
    ElMessage.success('移交验收单已删除')
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}

onMounted(async () => {
  // 从绿地档案「登记移交单」跳入时，预选绿地并自动打开登记弹窗
  if (route.query.create === '1' && filters.green_space_id) {
    try {
      presetSpace.value = await greenSpaceApi.detail(filters.green_space_id)
      formDialog.value?.open(null, presetSpace.value)
    } catch {
      // 绿地详情拉取失败时不阻断列表
    }
  }
})
</script>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.cell-main {
  font-weight: 500;
}

.cell-sub {
  color: #909399;
  font-size: 12px;
}

.area-checked {
  font-size: 12px;
  color: var(--gs-primary);
}

.text-muted {
  color: #c0c4cc;
}

.warranty-expiring {
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
