/**
 * Formatters Composable
 * Reusable formatting utilities
 */
import { useI18n } from 'vue-i18n';
export function useFormatters() {
    const { t } = useI18n();
    const formatDate = (date) => {
        if (!date)
            return '';
        const d = typeof date === 'string' ? new Date(date) : date;
        return d.toLocaleDateString();
    };
    const formatDateTime = (date) => {
        if (!date)
            return '';
        const d = typeof date === 'string' ? new Date(date) : date;
        return d.toLocaleString();
    };
    const formatFileSize = (bytes) => {
        if (bytes === 0)
            return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
    };
    const formatNumber = (num, decimals = 2) => {
        return num.toFixed(decimals);
    };
    const formatStatus = (status) => {
        const statusMap = {
            pending: t('status.pending'),
            running: t('status.running'),
            completed: t('status.completed'),
            failed: t('status.failed'),
            active: t('status.active'),
            archived: t('status.archived'),
        };
        return statusMap[status] || status;
    };
    return {
        formatDate,
        formatDateTime,
        formatFileSize,
        formatNumber,
        formatStatus,
    };
}
