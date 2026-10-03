<template>
  <div class="wall">
    <h1 class="serif">规则</h1>

    <!-- 源一：现行默认上限（settings，可维护；只对其后新发的愿望生效） -->
    <section class="card">
      <h3>现行默认上限</h3>
      <p class="tag">改这里只影响<strong>之后新发</strong>的愿望，不会回刷任何已发布/已认领愿望的写入带。</p>
      <p>当前默认上限：<strong>¥{{ cap === null ? '不限' : cap }}</strong></p>
      <input v-model="capInput" inputmode="decimal" placeholder="新的默认上限，如 300" />
      <p v-if="capErr" class="err">{{ capErr }}</p>
      <p v-if="capOk" class="warn">已更新，仅对新发愿望生效</p>
      <button @click="saveCap">保存默认上限</button>
    </section>

    <!-- 源二：每条愿望的写入带（冻结快照，与现行默认上限分源展示） -->
    <section class="card" style="margin-top:14px">
      <h3>该愿望写入带</h3>
      <p class="tag">以下为各愿望<strong>发布当时冻结</strong>的带，独立于上方现行默认上限。</p>
      <table v-if="bands.length" class="band-table">
        <thead>
          <tr><th>愿望</th><th>状态</th><th>估价</th><th>模式</th><th>写入时上限</th><th>判定</th></tr>
        </thead>
        <tbody>
          <tr v-for="b in bands" :key="b.id">
            <td>{{ b.title || '（无标题）' }}</td>
            <td>{{ b.status }}</td>
            <td>¥{{ b.band.price }}</td>
            <td>{{ modeText(b.band.mode) }}</td>
            <td>{{ b.band.cap === null ? '不限' : '¥' + b.band.cap }}</td>
            <td :class="b.band.verdict === 'warn' ? 'warn' : ''">
              {{ b.band.verdict === 'warn' ? warningText(b.band.warning) : '带内' }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="tag">暂无带估价的愿望。</p>
    </section>

    <ul style="margin-top:14px">
      <li v-for="(v,k) in rules" :key="k"><strong>{{ k }}</strong>：{{ v }}</li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { modeText, warningText, errorText } from '../band'
const rules = ref({})
const cap = ref(null)
const capInput = ref('')
const capErr = ref('')
const capOk = ref('')
const bands = ref([])
async function load() {
  const s = await api('/price-cap')
  cap.value = s.cap
  bands.value = await api('/price-cap/bands')
  rules.value = await api('/rules')
}
async function saveCap() {
  capErr.value = ''; capOk.value = ''
  const v = Number(capInput.value)
  if (!(v > 0)) { capErr.value = errorText('INVALID_PRICE'); return }
  try {
    const r = await api('/price-cap', { method: 'PUT', body: JSON.stringify({ cap: v }) })
    cap.value = r.cap; capInput.value = ''; capOk.value = true
    // 刷新写入带列表，确认历史行未被回刷
    bands.value = await api('/price-cap/bands')
  } catch (e) { capErr.value = errorText(e.message) }
}
onMounted(load)
</script>
