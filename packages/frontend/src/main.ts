import { VueQueryPlugin } from '@tanstack/vue-query';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import { createPinia } from 'pinia';
import 'uno.css';

import { createApp } from 'vue';
import { createI18n } from 'vue-i18n';

import App from './App.vue';
// Import i18n messages
import en from './locales/en.json';
import zhCN from './locales/zh-CN.json';
import router from './router/index.js';

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-CN': zhCN,
  },
});

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(Antd);
app.use(i18n);
app.use(VueQueryPlugin);

app.mount('#app');
