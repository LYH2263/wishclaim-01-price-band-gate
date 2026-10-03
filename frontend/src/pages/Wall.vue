<template>
  <div class="wall">
    <h1 class="serif">愿望墙</h1>
    <p class="tag">无顶栏 · 瀑布流 · 点卡片认领</p>
    <div class="masonry">
      <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
        <!-- 价位带角标：只读写入快照，不按现行默认重算 -->
        <span
          v-if="describeBand(w.band)"
          class="corner"
          :class="describeBand(w.band).over ? 'corner-warn' : 'corner-ok'"
          :title="describeBand(w.band).warningLabel || describeBand(w.band).modeLabel"
        >
          {{ describeBand(w.band).over ? describeBand(w.band).warningLabel : describeBand(w.band).modeLabel }}
        </span>
        <h3>{{ w.title || '（无标题）' }}</h3>
        <p>{{ w.note }}</p>
        <span class="tag">
          {{ w.status }} · {{ w.data_quality }}
          <template v-if="describeBand(w.band)"> · ¥{{ describeBand(w.band).price }} / 上限 ¥{{ describeBand(w.band).cap }}</template>
        </span>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { describeBand } from '../band'
const rows = ref([])
onMounted(async () => { rows.value = await api('/wishes') })
</script>
