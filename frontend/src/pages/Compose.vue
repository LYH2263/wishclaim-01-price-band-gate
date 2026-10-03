<template>
  <div class="wall">
    <h1 class="serif">发愿望</h1>
    <input v-model="title" placeholder="标题" />
    <textarea v-model="note" rows="4" placeholder="备注" />
    <label class="tag" for="price">估价（选填，留空则不设价位带）</label>
    <input id="price" v-model="price" inputmode="decimal" placeholder="如 199" />
    <div v-if="hasPrice" class="mode-row">
      <label><input type="radio" value="soft" v-model="bandMode" /> 软门禁（超额可发布，带提醒）</label>
      <label><input type="radio" value="hard" v-model="bandMode" /> 硬门禁（超额整单拒绝）</label>
    </div>
    <p class="tag" v-if="cap !== null">现行默认上限：¥{{ cap }}（仅写入时取一次，之后不回刷）</p>
    <p v-if="err" class="err">{{ err }}</p>
    <button @click="submit">发布</button>
  </div>
</template>
<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { errorText } from '../band'
const router = useRouter()
const title = ref('')
const note = ref('')
const price = ref('')
const bandMode = ref('soft')
const cap = ref(null)
const err = ref('')
const hasPrice = ref(false)
onMounted(async () => {
  try { const s = await api('/price-cap'); cap.value = s.cap } catch {}
})
watch(price, (v) => { hasPrice.value = String(v).trim() !== '' })
async function submit() {
  err.value = ''
  const body = { title: title.value, note: note.value }
  const raw = String(price.value).trim()
  // 未填估价：不带 price / band_mode，字段集合与改造前兼容
  if (raw !== '') {
    const num = Number(raw)
    if (!Number.isFinite(num) || num <= 0) {
      err.value = errorText('INVALID_PRICE')
      return
    }
    body.price = num
    body.band_mode = bandMode.value
  }
  try {
    const r = await api('/wishes', { method: 'POST', body: JSON.stringify(body) })
    router.push('/wishes/' + r.id)
  } catch (e) { err.value = errorText(e.message) }
}
</script>
