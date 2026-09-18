<template>
  <div class="page">
    <PageHeader title="绿地移交验收" description="登记新建绿地移交信息，组织验收核对，跟踪缺陷整改与质保回访">
      <template #actions>
        <el-button type="primary" :icon="'Plus'" @click="formDialog.open()">登记验收单</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <div class="filter-bar">
        <el-input v-model="filters.keyword" placeholder="单号 / 移交方 / 接收单位" clearable
                  :prefix-icon="'Search'" @keyup.enter="search" @clear="search" />
        <div style="width: 220px">
          <GreenSpaceSelect v-model="filters.green_space_id" placeholder="按绿地筛选" @update:model-value="search" />
        </div>
        <el-select v-model="filters.status" placeholder="验收状态" clearable @change="search">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-checkbox v-model="filters.defect_open" label="仅有待整改缺陷" border @change="search" />
        <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
        <el-button :icon="'RefreshLeft'" @click="reset">重置</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <StatCard label="验收单" :value="formatNumber(summary?.total_count ?? 0)" unit="份"
                :hint="`待验收 ${summary?.by_status?.pending ?? 0} 份`" icon="DocumentChecked" />
      <StatCard label="整改中" :value="formatNumber(summary?.by_status?.rectifying ?? 0)" unit="份"
                :hint="`待整改缺陷 ${formatNumber(summary?.open_defect_count ?? 0)} 项`"
                tone="warning" icon="Tools" />
      <StatCard label="质保期内" :value="formatNumber(summary?.by_status?.passed ?? 0)" unit="份"
                :hint="`处理中回访 ${formatNumber(summary?.open_follow_up_count ?? 0)} 条`"
                tone="info" icon="FirstAidKit" />
      <StatCard label="已办结" :value="formatNumber(summary?.by_status?.closed ?? 0)" unit="份"
                hint="质保责任已终结" icon="CircleCheck" />
    </div>

    <div class="panel">
      <div class="table-toolbar">
        <span class="summary-text">
          共 <strong>{{ meta.total }}</strong> 份验收单，
          待整改缺陷 <strong>{{ formatNumber(summary?.open_defect_count ?? 0) }}</strong> 项
        </span>
        <el-button :icon="'Refresh'" text @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column prop="acceptance_no" label="验收单号" width="160" />
        <el-table-column label="所属绿地" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.green_space?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="handover_party" label="移交方" min-width="170" show-overflow-tooltip />
        <el-table-column label="绿化面积" width="110" align="right">
          <template #default="{ row }">{{ formatArea(row.area_sqm) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <EnumTag group="acceptance_status" :value="row.status" :label="row.status_label" />
          </template>
        </el-table-column>
        <el-table-column prop="acceptance_date" label="验收日期" width="105">
          <template #default="{ row }">{{ row.acceptance_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="质保截止" width="105">
          <template #default="{ row }">
            <span :class="{ 'warranty-expired': row.is_warranty_expired }">
              {{ row.warranty_end_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="待整改 / 回访" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.open_defect_count" type="warning" size="small" effect="plain">
              缺陷 {{ row.open_defect_count }}
            </el-tag>
            <el-tag v-if="row.open_follow_up_count" type="danger" size="small" effect="plain"
                    style="margin-left: 4px">
              回访 {{ row.open_follow_up_count }}
            </el-tag>
            <span v-if="!row.open_defect_count && !row.open_follow_up_count">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row)">详情</el-button>
            <el-button link type="primary" :disabled="row.status === 'closed'"
                       @click="formDialog.open(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.status === 'closed'"
                       @click="remove(row)">删除</el-button>
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

    <AcceptanceFormDialog ref="formDialog" @saved="load" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { handoverAcceptanceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import GreenSpaceSelect from '@/components/common/GreenSpaceSelect.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { useListQuery } from '@/composables/useListQuery'
import { formatArea, formatNumber } from '@/utils/format'

import AcceptanceFormDialog from './AcceptanceFormDialog.vue'

const route = useRoute()
const router = useRouter()
const formDialog = ref(null)

const { options: statusOptions } = useEnumOptions('acceptance_status')

const { filters, meta, items, summary, loading, load, search, resetFilters, handlePageChange, handleSizeChange } =
  useListQuery(handoverAcceptanceApi.list, {
    initialFilters: {
      keyword: '',
      green_space_id: route.query.green_space_id ? Number(route.query.green_space_id) : null,
      status: '',
      defect_open: false,
    },
  })

function goDetail(row) {
  router.push({ name: 'acceptance-detail', params: { id: row.id } })
}

function reset() {
  resetFilters()
}

async function remove(row) {
  const doDelete = async (force) => {
    await handoverAcceptanceApi.remove(row.id, force ? { force: 'true' } : undefined)
    ElMessage.success('移交验收单已删除')
    await load()
  }
  try {
    await ElMessageBox.confirm(`确认删除验收单「${row.acceptance_no}」吗？`, '删除确认', {
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
</script>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.warranty-expired {
  color: #f56c6c;
}
</style>
