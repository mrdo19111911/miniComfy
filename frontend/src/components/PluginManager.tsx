/**
 * PluginManager - Modal for viewing, installing, activating/deactivating, and removing plugins.
 * Uses hierarchical project → plugins layout matching the backend API.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE } from '../constants';
import type { ProjectInfo } from '../types';

export interface PluginManagerProps {
  visible: boolean;
  onClose: () => void;
  onReload?: () => void;
}

export function PluginManager({ visible, onClose, onReload }: PluginManagerProps) {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPlugins = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/plugins`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ProjectInfo[] = await res.json();
      setProjects(data);
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
      setConfirmDelete(null);
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

  const doAction = async (url: string, method: string, successMessage: string) => {
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE}${url}`, { method });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setSuccessMsg(successMessage);
      setConfirmDelete(null);
      await fetchPlugins();
      onReload?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
    }
  };

  const handleActivatePlugin = (project: string, plugin: string) =>
    doAction(`/api/plugins/${project}/${plugin}/activate`, 'POST', `Plugin '${plugin}' activated.`);

  const handleDeactivatePlugin = (project: string, plugin: string) =>
    doAction(`/api/plugins/${project}/${plugin}/deactivate`, 'POST', `Plugin '${plugin}' deactivated.`);

  const handleDeletePlugin = (project: string, plugin: string) =>
    doAction(`/api/plugins/${project}/${plugin}`, 'DELETE', `Plugin '${plugin}' deleted.`);

  const handleActivateProject = (project: string) =>
    doAction(`/api/plugins/${project}/activate`, 'POST', `All plugins in '${project}' activated.`);

  const handleDeactivateProject = (project: string) =>
    doAction(`/api/plugins/${project}/deactivate`, 'POST', `All plugins in '${project}' deactivated.`);

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
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setSuccessMsg(data.message || `Plugin '${data.name}' installed.`);
      await fetchPlugins();
      onReload?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Install failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const toggleCollapse = (project: string) =>
    setCollapsed((prev) => ({ ...prev, [project]: !prev[project] }));

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
          width: 620,
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
          <div style={{ background: '#3B1111', color: '#EF4444', padding: '8px 20px', fontSize: 12, borderBottom: '1px solid #333' }}>
            {error}
          </div>
        )}
        {successMsg && (
          <div style={{ background: '#0F2E1A', color: '#10B981', padding: '8px 20px', fontSize: 12, borderBottom: '1px solid #333' }}>
            {successMsg}
          </div>
        )}

        {/* Plugin list — hierarchical */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loading && (
            <div style={{ color: '#888', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
              Loading plugins...
            </div>
          )}
          {!loading && projects.length === 0 && (
            <div style={{ color: '#888', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
              No plugins installed.
            </div>
          )}

          {projects.map((proj) => {
            const isCollapsed = collapsed[proj.project];
            const activeCount = proj.plugins.filter((p) => p.state === 'active').length;
            const totalCount = proj.plugins.length;

            return (
              <div key={proj.project} style={{ borderBottom: '1px solid #2A2A2A' }}>
                {/* Project header */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 20px',
                    cursor: 'pointer',
                    background: '#222',
                  }}
                  onClick={() => toggleCollapse(proj.project)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: '#888', fontSize: 10, width: 12 }}>
                      {isCollapsed ? '\u25B6' : '\u25BC'}
                    </span>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: proj.status === 'ok' ? '#10B981' : '#EF4444',
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ color: '#eee', fontWeight: 600, fontSize: 13 }}>
                      {proj.project}
                    </span>
                    <span style={{ color: '#666', fontSize: 11 }}>
                      v{proj.manifest.version}
                    </span>
                    <span style={{ color: '#555', fontSize: 10 }}>
                      ({activeCount}/{totalCount} active)
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }} onClick={(e) => e.stopPropagation()}>
                    {activeCount < totalCount && (
                      <button
                        onClick={() => handleActivateProject(proj.project)}
                        style={{ ...smallBtnStyle, color: '#10B981', borderColor: '#10B981' }}
                      >
                        Activate All
                      </button>
                    )}
                    {activeCount > 0 && (
                      <button
                        onClick={() => handleDeactivateProject(proj.project)}
                        style={{ ...smallBtnStyle, color: '#FBBF24', borderColor: '#FBBF24' }}
                      >
                        Deactivate All
                      </button>
                    )}
                  </div>
                </div>

                {/* Project description */}
                {!isCollapsed && proj.manifest.description && (
                  <div style={{ padding: '2px 20px 4px 48px', color: '#777', fontSize: 11 }}>
                    {proj.manifest.description}
                  </div>
                )}

                {/* Project error */}
                {!isCollapsed && proj.error && (
                  <div style={{ padding: '2px 20px 4px 48px', color: '#EF4444', fontSize: 11 }}>
                    Error: {proj.error}
                  </div>
                )}

                {/* Plugins list */}
                {!isCollapsed &&
                  proj.plugins.map((plugin) => {
                    const pluginName = plugin.id.split('/')[1] || plugin.id;
                    const isActive = plugin.state === 'active';
                    const isConfirmingDelete = confirmDelete === plugin.id;

                    return (
                      <div
                        key={plugin.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '5px 20px 5px 48px',
                          opacity: isActive ? 1 : 0.6,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: isActive ? '#10B981' : '#666',
                              border: isActive ? 'none' : '1px solid #888',
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ color: '#ccc', fontSize: 12 }}>
                            {pluginName}
                          </span>
                          <span style={{ color: '#555', fontSize: 10 }}>
                            {plugin.node_types.join(', ')}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                          {isActive ? (
                            <button
                              onClick={() => handleDeactivatePlugin(proj.project, pluginName)}
                              style={smallBtnStyle}
                            >
                              Deactivate
                            </button>
                          ) : (
                            <>
                              <button
                                onClick={() => handleActivatePlugin(proj.project, pluginName)}
                                style={{ ...smallBtnStyle, color: '#10B981', borderColor: '#10B981' }}
                              >
                                Activate
                              </button>
                              {isConfirmingDelete ? (
                                <>
                                  <button
                                    onClick={() => handleDeletePlugin(proj.project, pluginName)}
                                    style={{ ...smallBtnStyle, background: '#7F1D1D', borderColor: '#991B1B', color: '#FCA5A5' }}
                                  >
                                    Confirm
                                  </button>
                                  <button
                                    onClick={() => setConfirmDelete(null)}
                                    style={smallBtnStyle}
                                  >
                                    Cancel
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => setConfirmDelete(plugin.id)}
                                  style={{ ...smallBtnStyle, color: '#EF4444', borderColor: '#EF4444' }}
                                >
                                  Delete
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            );
          })}
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

const smallBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #555',
  borderRadius: 3,
  color: '#999',
  padding: '2px 8px',
  fontSize: 10,
  cursor: 'pointer',
};
