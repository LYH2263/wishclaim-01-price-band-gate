<template>
  <div class="wall">
    <h1 class="serif">愿望墙</h1>
    <p class="tag">无顶栏 · 瀑布流 · 点卡片认领</p>
    <div class="masonry">
      <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
        <span
          v-if="w.band"
          class="badge"
          :class="{ over: !w.band.within }"
          :title="w.band.warning ? warningText(w.band.warning) : modeText(w.band.band_mode)"
        >
          {{ modeText(w.band.band_mode) }}{{ w.band.within ? '' : ' · 超额' }}
        </span>
        <h3>{{ w.title || '（无标题）' }}</h3>
        <p>{{ w.note }}</p>
        <span v-if="w.band" class="tag">{{ formatPrice(w.band.estimate) }} / 上限 {{ formatPrice(w.band.cap) }}</span>
        <span class="tag">{{ w.status }} · {{ w.data_quality }}</span>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { formatPrice, modeText, warningText } from '../band'
const rows = ref([])
onMounted(async () => { rows.value = await api('/wishes') })
</script>
