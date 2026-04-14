import React, { useState } from 'react';
import '../styles/AdminModal.css';

const AdminModal = ({ isOpen, onClose }) => {
    const [password, setPassword] = useState('');
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [logs, setLogs] = useState([]);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    
    // Состояния для панели сброса
    const [resetId, setResetId] = useState('');
    const [resetMessage, setResetMessage] = useState('');
    
    // Состояния для массового сброса
    const [bulkIds, setBulkIds] = useState('');
    const [bulkMessage, setBulkMessage] = useState('');
    const [bulkLoading, setBulkLoading] = useState(false);

    if (!isOpen) return null;

    const fetchLogs = async () => {
        try {
            const API_URL = "";
            const res = await fetch(`${API_URL}/admin/logs?password=${password}`);

            if (res.ok) {
                const data = await res.json();
                setLogs(data);
                setIsAuthenticated(true);
            } else {
                if (res.status === 403) {
                    setError('Неверный пароль');
                } else {
                    const text = await res.text();
                    setError(`Ошибка ${res.status}: ${text}`);
                }
            }
        } catch (err) {
            setError('Ошибка соединения с сервером');
        }
        setLoading(false);
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        await fetchLogs();
    };

    const handleResetGeocode = async (idToReset) => {
        if (!window.confirm(`Вы уверены, что хотите сбросить геоданные для новости #${idToReset}? Геокодер сразу начнет обработку.`)) return;
        try {
            const res = await fetch(`/admin/news/${idToReset}/reset-geocode?password=${password}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                const coordsText = data.coords ? `${data.coords[0]}, ${data.coords[1]}` : 'Не найдены';
                setResetMessage(`✅ Новость #${idToReset} обработана: ${data.address} → ${coordsText}`);
                await fetchLogs(); // Обновляем таблицу логов сразу
                
                // Если сбросили текущую открытую новость, перезагружаем страницу через 1 секунду
                const currentPath = window.location.hash;
                if (currentPath.includes(`/news/${idToReset}`)) {
                    setResetMessage(prev => prev + '\n🔄 Страница будет обновлена...');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                }
            } else {
                const errData = await res.json().catch(() => ({}));
                setResetMessage(`❌ Ошибка: ${res.status} - ${errData.detail || 'Неизвестная ошибка'}`);
            }
        } catch (err) {
            setResetMessage('❌ Сетевая ошибка при попытке сброса');
        }
    };

    const handleClose = () => {
        setIsAuthenticated(false);
        setPassword('');
        setError('');
        onClose();
    };

    const handleForceRssUpdate = async () => {
        if (!window.confirm('Запустить принудительное обновление RSS-ленты?')) return;
        try {
            const res = await fetch(`/admin/force-rss-update?password=${password}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                alert(`✅ ${data.message}`);
                // Обновляем логи через 5 секунд (когда парсинг завершится)
                setTimeout(() => fetchLogs(), 5000);
            } else {
                const errData = await res.json().catch(() => ({}));
                alert(`❌ Ошибка: ${res.status} - ${errData.detail || 'Неизвестная ошибка'}`);
            }
        } catch (err) {
            alert('❌ Сетевая ошибка при попытке обновления RSS');
        }
    };

    const handleBulkReset = async () => {
        if (!bulkIds.trim()) {
            setBulkMessage('❌ Введите ID новостей');
            return;
        }
        if (!window.confirm(`Сбросить и заново геокодировать новости: ${bulkIds}?`)) return;
        
        setBulkLoading(true);
        setBulkMessage('⏳ Обработка...');
        try {
            const res = await fetch(`/admin/bulk-reset-geocode?ids=${encodeURIComponent(bulkIds)}&password=${password}`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                const successCount = data.processed || 0;
                const notFound = data.not_found?.length || 0;
                const errors = data.errors?.length || 0;
                
                let msg = `✅ Обработано: ${successCount}`;
                if (notFound > 0) msg += ` | ❌ Не найдено: ${notFound}`;
                if (errors > 0) msg += ` | ⚠️ Ошибки: ${errors}`;
                
                // Показываем первые несколько результатов
                if (data.results?.length > 0) {
                    msg += '\n\nПримеры:';
                    data.results.slice(0, 5).forEach(r => {
                        const coords = r.coords ? `${r.coords[0].toFixed(4)}, ${r.coords[1].toFixed(4)}` : 'НЕТ';
                        msg += `\n#${r.id}: ${r.address} → ${coords}`;
                    });
                }
                
                setBulkMessage(msg);
                await fetchLogs();
            } else {
                const errData = await res.json().catch(() => ({}));
                setBulkMessage(`❌ Ошибка: ${res.status} - ${errData.detail || 'Неизвестная ошибка'}`);
            }
        } catch (err) {
            setBulkMessage('❌ Сетевая ошибка при массовом сбросе');
        }
        setBulkLoading(false);
    };

    return (
        <div className="admin-modal-overlay">
            <div className={`admin-modal-content ${isAuthenticated ? 'admin-modal-large' : 'admin-modal-small'}`}>

                <button className="admin-close-btn" onClick={handleClose}>×</button>

                {!isAuthenticated ? (
                    <div className="admin-login-box">
                        <h2>Админ-панель</h2>
                        <form onSubmit={handleLogin}>
                            <input
                                type="password"
                                placeholder="Пароль"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoFocus
                            />
                            <button type="submit" disabled={loading}>
                                {loading ? "Проверка..." : "Войти"}
                            </button>
                        </form>
                        {error && <p className="admin-error">{error}</p>}
                    </div>
                ) : (
                    <div className="admin-logs-view">
                        <div className="admin-header">
                            <h2>Журнал работы геокодера</h2>
                            <button className="rss-update-btn" onClick={handleForceRssUpdate}>
                                🔄 Обновить RSS
                            </button>
                        </div>

                        {/* Панель ручного сброса координат */}
                        <div className="admin-reset-panel">
                            <h4>Ручной сброс геокодера (одна новость)</h4>
                            <div className="reset-controls">
                                <input
                                    type="number"
                                    placeholder="ID новости"
                                    value={resetId}
                                    onChange={(e) => {
                                        setResetId(e.target.value);
                                        setResetMessage('');
                                    }}
                                />
                                <button
                                    onClick={() => handleResetGeocode(resetId)}
                                    disabled={!resetId}
                                    className="reset-btn"
                                >
                                    Сбросить адрес
                                </button>
                            </div>

                            {resetMessage && <div className="reset-msg">{resetMessage}</div>}
                        </div>

                        {/* Панель массового сброса координат */}
                        <div className="admin-bulk-reset-panel">
                            <h4>Массовый сброс геокодера</h4>
                            <p className="bulk-hint">Формат: <code>85, 90-100, 105</code> — отдельные ID или диапазоны</p>
                            <div className="reset-controls">
                                <input
                                    type="text"
                                    placeholder="85, 90-100, 105"
                                    value={bulkIds}
                                    onChange={(e) => {
                                        setBulkIds(e.target.value);
                                        setBulkMessage('');
                                    }}
                                    className="bulk-input"
                                />
                                <button
                                    onClick={handleBulkReset}
                                    disabled={bulkLoading || !bulkIds.trim()}
                                    className="bulk-reset-btn"
                                >
                                    {bulkLoading ? '⏳ Обработка...' : '🔄 Массовый сброс'}
                                </button>
                            </div>

                            {bulkMessage && <pre className="bulk-msg">{bulkMessage}</pre>}
                        </div>

                        <div className="admin-table-wrapper">
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Новость</th>
                                        <th>Время парсинга</th>
                                        <th>Статус геокодирования</th>
                                        <th>Найденный адрес</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map(log => (
                                        <tr key={log.id}>
                                            <td>{log.id}</td>
                                            <td className="admin-title-cell">{log.title}</td>
                                            <td>{log.parsed_at || "—"}</td>
                                            <td>{log.geocoded_at || "⏳ Ожидание"}</td>
                                            <td className={log.address === 'NOT_FOUND' ? "addr-error" : log.address ? "addr-success" : ""}>
                                                {log.address === 'NOT_FOUND' ? " Не найдено" :
                                                    log.address ? ` ${log.address}` : "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AdminModal;
