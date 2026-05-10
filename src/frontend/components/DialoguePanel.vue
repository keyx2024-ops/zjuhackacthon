<template>
  <div class="dialogue-container">
    <div v-if="!integrationResult" class="empty-state">
      <div class="empty-state-icon">💬</div>
      <div>请先执行教材整合</div>
      <div style="font-size: 12px; margin-top: 4px;">
        整合后即可与系统进行多轮对话以优化整合方案
      </div>
    </div>

    <template v-else>
      <div class="quick-actions">
        <div class="quick-action-title">💡 快捷操作（点击发送）：</div>
        <el-button-group>
          <el-button size="small" @click="sendQuickMessage('请解释为什么要合并这些知识点？')">
            解释合并理由
          </el-button>
          <el-button size="small" @click="sendQuickMessage('当前压缩比合理吗？')">
            评估压缩比
          </el-button>
          <el-button size="small" @click="sendQuickMessage('哪些重要知识点可能被遗漏？')">
            遗漏检查
          </el-button>
        </el-button-group>
      </div>

      <div ref="messagesContainer" class="messages-container">
        <div v-if="messages.length === 0" class="empty-message">
          <div>开始对话以优化整合方案</div>
          <div style="font-size: 12px; margin-top: 8px; color: #909399;">
            示例："为什么要合并 X 和 Y？" / "取消合并 A 和 B" / "保留 C 这个知识点"
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.message_id"
          class="chat-message"
          :class="msg.role"
        >
          <div class="message-content">{{ msg.content }}</div>
          <div v-if="msg.metadata?.actions?.length" class="message-actions">
            <div class="action-label">已执行操作：</div>
            <div v-for="(action, idx) in msg.metadata.actions" :key="idx" class="action-item">
              ✓ {{ action.action_type }}
            </div>
          </div>
          <div v-if="msg.metadata?.graph_updated" class="graph-updated-tag">
            🔄 知识图谱已更新
          </div>
        </div>
      </div>

      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入消息（按 Enter 发送，Shift+Enter 换行）..."
          @keydown.enter.prevent.exact="sendMessage"
        />
        <el-button
          type="primary"
          :loading="sending"
          :disabled="!inputMessage.trim()"
          @click="sendMessage"
          style="margin-top: 8px;"
        >
          发送
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import { dialogueApi } from '../services/api.js';

const props = defineProps({
  integrationResult: Object,
});

const emit = defineEmits(['decisions-modified']);

const messages = ref([]);
const inputMessage = ref('');
const sending = ref(false);
const sessionId = ref(null);
const messagesContainer = ref(null);

async function sendMessage() {
  if (!inputMessage.value.trim() || sending.value) return;

  const userMessage = {
    message_id: Date.now().toString(),
    role: 'user',
    content: inputMessage.value,
    metadata: {},
  };
  messages.value.push(userMessage);

  const messageText = inputMessage.value;
  inputMessage.value = '';
  sending.value = true;
  scrollToBottom();

  try {
    const response = await dialogueApi.chat(messageText, sessionId.value);
    sessionId.value = response.session_id;
    messages.value.push(response.message);

    if (response.graph_updated) {
      ElMessage.success('知识图谱已根据您的反馈更新');
      emit('decisions-modified');
    }
    scrollToBottom();
  } catch (error) {
    ElMessage.error(`对话失败：${error.message}`);
  } finally {
    sending.value = false;
  }
}

function sendQuickMessage(text) {
  inputMessage.value = text;
  sendMessage();
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}
</script>

<style scoped>
.dialogue-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 500px;
}

.quick-actions {
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}

.quick-action-title {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 10px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  margin-bottom: 12px;
  min-height: 200px;
  max-height: 400px;
}

.empty-message {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
  font-size: 13px;
}

.message-content {
  white-space: pre-wrap;
  line-height: 1.65;
  color: var(--text-primary);
}

.message-actions {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 12px;
}

.action-label {
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.action-item {
  color: var(--success);
}

.graph-updated-tag {
  background: var(--success);
  color: white;
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 999px;
  display: inline-block;
  margin-top: 6px;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.input-area {
  flex-shrink: 0;
}

.input-area :deep(.el-textarea__inner) {
  border-radius: var(--radius-md);
  border-color: var(--border);
  resize: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.input-area :deep(.el-textarea__inner:focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.empty-state {
  text-align: center;
  padding: 48px 20px;
  color: var(--text-tertiary);
}

.empty-state-icon {
  font-size: 42px;
  margin-bottom: 12px;
  opacity: 0.6;
}
</style>
