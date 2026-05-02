<template>
  <div class="home-wrap">
    <transition name="fade" mode="out-in">
      <RepoInput v-if="!analyzed" @success="onRepoSuccess" key="repo-input" />
      <ChatWindow v-else :repo-slug="repoSlug" key="chat-window" />
    </transition>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import RepoInput from '../components/RepoInput.vue'
import ChatWindow from '../components/ChatWindow.vue'

const gitchat = inject('gitchat')
const analyzed = gitchat.analyzed
const repoSlug = gitchat.repoSlug

const onRepoSuccess = (payload) => {
  gitchat.setRepoAnalyzed(payload)
}
</script>

<style scoped>
.home-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
