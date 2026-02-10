/**
 * PluginManager - Modal for viewing, installing, and removing plugins.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE } from '../constants';

export interface PluginManagerProps {
  visible: boolean;
  onClose: () => void;
  onReload?: () => void;
}

interface PluginInfo {
  name: string;
  version: string;
  description: string;
  status: string;
  error: string | null;
}

export function PluginManager({ visible, onClose, onReload }: PluginManagerProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPlugins = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/plugins`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PluginInfo[] = await res.json();
      setPlugins(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch plugins');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (visible) {
      fetchPlugins();
      setSuccessMsg(null);
      setConfirmRemove(null);
    }
  }, [visible, fetchPlugins]);

  // Close on Escape
  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [visible, onClose]);

  const handleInstall = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/plugins/install`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      setSuccessMsg(data.message || `Plugin '${data.name}' installed.`);
      await fetchPlugins();
      onReload?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Install failed');
    } finally {
      setUploading(false);
      // Reset file input so the same file can be selected again
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemove = async (pluginName: string) => {
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/plugins/${encodeURIComponent(pluginName)}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      setSuccessMsg(`Plugin '${pluginName}' removed.`);
      setConfirmRemove(null);
      await fetchPlugins();
      onReload?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Remove failed');
    }
  };

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: '#1E1E1E',
          border: '1px solid #333',
          borderRadius: 8,
          width: 560,
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid #333',
          }}
        >
          <span style={{ color: '#eee', fontWeight: 700, fontSize: 16 }}>
            Plugin Manager
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#888',
              fontSize: 20,
              cursor: 'pointer',
              lineHeight: 1,
              padding: '0 4px',
            }}
            title="Close"
          >
            x
          </button>
        </div>

        {/* Messages */}
        {error && (
          <div
            style={{
              background: '#3B1111',
              color: '#EF4444',
              padding: '8px 20px',
              fontSize: 12,
              borderBottom: '1px solid #333',
            }}
          >
            {error}
          </div>
        )}
        {successMsg && (
          <div
            style={{
              background: '#0F2E1A',
              color: '#10B981',
              padding: '8px 20px',
              fontSize: 12,
              borderBottom: '1px solid #333',
            }}
          >
            {successMsg}
          </div>
        )}

        {/* Plugin list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
          {loading && (
            <div style={{ color: '#888', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
              Loading plugins...
            </div>
          )}
          {!loading && plugins.length === 0 && (
            <div style={{ color: '#888', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
              No plugins installed.
            </div>
          )}
          {plugins.map((plugin) => (
            <div
              key={plugin.name}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: '1px solid #2A2A2A',
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: plugin.status === 'ok' ? '#10B981' : '#EF4444',
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ color: '#eee', fontWeight: 600, fontSize: 13 }}>
                    {plugin.name}
                  </span>
                  <span style={{ color: '#666', fontSize: 11 }}>v{plugin.version}</span>
                </div>
                <div
                  style={{
                    color: '#999',
                    fontSize: 12,
                    marginTop: 4,
                    paddingLeft: 16,
                  }}
                >
                  {plugin.description || 'No description'}
                </div>
                {plugin.error && (
                  <div
                    style={{
                      color: '#EF4444',
                      fontSize: 11,
                      marginTop: 4,
                      paddingLeft: 16,
                    }}
                  >
                    Error: {plugin.error}
                  </div>
                )}
              </div>
              <div style={{ flexShrink: 0, marginLeft: 12 }}>
                {confirmRemove === plugin.name ? (
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      onClick={() => handleRemove(plugin.name)}
                      style={{
                        ...btnStyle,
                        background: '#7F1D1D',
                        borderColor: '#991B1B',
                        color: '#FCA5A5',
                        fontSize: 11,
                        padding: '4px 10px',
                      }}
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setConfirmRemove(null)}
                      style={{
                        ...btnStyle,
                        fontSize: 11,
                        padding: '4px 10px',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmRemove(plugin.name)}
                    style={{
                      ...btnStyle,
                      fontSize: 11,
                      padding: '4px 10px',
                    }}
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer with install button */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid #333',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleInstall}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{
              ...btnStyle,
              background: '#2563EB',
              borderColor: '#3B82F6',
              color: '#fff',
            }}
          >
            {uploading ? 'Uploading...' : 'Install Plugin'}
          </button>
          <span style={{ color: '#666', fontSize: 11 }}>
            Upload a .zip file containing a plugin with manifest.json
          </span>
        </div>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: '#333',
  border: '1px solid #555',
  borderRadius: 4,
  color: '#ccc',
  padding: '6px 14px',
  fontSize: 12,
  cursor: 'pointer',
};
