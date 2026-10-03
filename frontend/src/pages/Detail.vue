<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>

    <div v-if="w.band" class="band-box" :class="{ over: !w.band.within }">
      <p class="tag">该愿望写入带（发布时快照，不随后续默认变动）</p>
      <p>
        估价 {{ formatPrice(w.band.estimate) }} · 写入上限 {{ formatPrice(w.band.cap) }} ·
        {{ modeText(w.band.band_mode) }} · {{ w.band.within ? '上限内' : '超额' }}
      </p>
      <p v-if="w.band.warning" class="warn">⚠ {{ warningText(w.band.warning) }}（{{ w.band.warning }}）</p>
    </div>

    <p class="tag">状态 {{ w.status }} · 认领人 {{ w.claimer || '—' }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <input v-model="claimer" placeholder="你的名字" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button @click="claim">认领锁定</button>
      <button class="ghost" @click="release">释放</button>
      <button class="ghost" @click="fulfill">核销完成</button>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { formatPrice, modeText, warningText } from '../band'
const props = defineProps({ id: String })
const w = ref({})
const claimer = ref('访客')
const err = ref('')
async function load() { w.value = await api('/wishes/' + props.id) }
async function claim() {
  err.value=''; try { await api('/wishes/'+props.id+'/claim',{method:'POST',body:JSON.stringify({claimer:claimer.value})}); await load() } catch(e){ err.value=e.message }
}
async function release() {
  err.value=''; try { await api('/wishes/'+props.id+'/release',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message }
}
async function fulfill() {
  err.value=''; try { await api('/wishes/'+props.id+'/fulfill',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message }
}
onMounted(load)
</script>
