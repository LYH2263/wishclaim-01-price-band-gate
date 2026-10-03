<template>
  <div class="wall">
    <h1 class="serif">发愿望</h1>
    <input v-model="title" placeholder="标题" />
    <textarea v-model="note" rows="4" placeholder="备注" />
    <input v-model="estimate" type="number" min="0" step="0.01" placeholder="估价（元，可不填）" />
    <select v-model="bandMode" :disabled="!estimate">
      <option value="soft">软门禁：超额仍可写入并标记提醒</option>
      <option value="hard">硬门禁：超额整单拒绝</option>
    </select>
    <button @click="submit">发布</button>
    <p v-if="warn" class="warn">⚠ {{ warningText(warn) }}</p>
    <p v-if="err" class="err">{{ err }}</p>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { warningText } from '../band'
const router = useRouter()
const title = ref('')
const note = ref('')
const estimate = ref('')
const bandMode = ref('soft')
const warn = ref('')
const err = ref('')
async function submit() {
  warn.value = ''; err.value = ''
  const body = { title: title.value, note: note.value }
  // Only attach estimate fields when filled: legacy-compatible field set.
  if (estimate.value !== '') {
    body.estimate = Number(estimate.value)
    body.band_mode = bandMode.value
  }
  try {
    const r = await api('/wishes', { method: 'POST', body: JSON.stringify(body) })
    if (r.warning) warn.value = r.warning
    router.push('/wishes/' + r.id)
  } catch (e) { err.value = warningText(e.message) }
}
</script>
