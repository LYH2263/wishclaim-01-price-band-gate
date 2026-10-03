<template>
  <div class="wall">
    <h1 class="serif">规则</h1>
    <ul>
      <li v-for="(v,k) in rules.rules" :key="k"><strong>{{ k }}</strong>：{{ v }}</li>
    </ul>

    <section class="card">
      <h3 class="serif">现行默认上限</h3>
      <p class="tag">来源：settings · {{ rules.price_cap?.default_source }} —— 仅对之后新发的愿望生效，不回刷历史愿望。</p>
      <p>默认上限：{{ formatPrice(rules.price_cap?.default_cap) }}</p>
      <div style="display:flex;gap:8px">
        <input v-model="cap" type="number" min="0" step="0.01" placeholder="新默认上限" />
        <button @click="saveCap">更新默认</button>
      </div>
      <p v-if="capErr" class="err">{{ capErr }}</p>
      <p v-if="capOk" class="tag">已更新；已有愿望的写入带不变。</p>
    </section>

    <section class="card">
      <h3 class="serif">该愿望写入带（发布时落库快照）</h3>
      <p class="tag">与上方「现行默认上限」分源：每行取各自发布时钉住的快照，认领/改默认都不重算。</p>
      <table class="band-table">
        <thead><tr><th>#</th><th>愿望</th><th>估价</th><th>写入上限</th><th>门禁</th><th>结果/提醒</th></tr></thead>
        <tbody>
          <tr v-for="row in rules.price_cap?.written || []" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.title }}</td>
            <td>{{ formatPrice(row.band.estimate) }}</td>
            <td>{{ formatPrice(row.band.cap) }}</td>
            <td>{{ modeText(row.band.band_mode) }}</td>
            <td>
              <span v-if="row.band.within">上限内</span>
              <span v-else class="warn">⚠ {{ warningText(row.band.warning) }}</span>
            </td>
          </tr>
          <tr v-if="!(rules.price_cap?.written || []).length"><td colspan="6" class="tag">暂无填写估价的愿望</td></tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { formatPrice, modeText, warningText } from '../band'
const rules = ref({})
const cap = ref('')
const capErr = ref('')
const capOk = ref(false)
async function load() { rules.value = await api('/rules') }
async function saveCap() {
  capErr.value = ''; capOk.value = false
  try {
    await api('/settings/price_cap', { method: 'PUT', body: JSON.stringify({ cap: Number(cap.value) }) })
    capOk.value = true; cap.value = ''; await load()
  } catch (e) { capErr.value = warningText(e.message) }
}
onMounted(load)
</script>
