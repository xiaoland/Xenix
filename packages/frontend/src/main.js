import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createI18n } from 'vue-i18n';
import { VueQueryPlugin } from '@tanstack/vue-query';
import Antd from 'ant-design-vue';
import router from './router/index.js';
import App from './App.vue';
import 'ant-design-vue/dist/reset.css';
import 'uno.css';
// Import i18n messages
import en from './locales/en.json';
import zhCN from './locales/zh-CN.json';
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
