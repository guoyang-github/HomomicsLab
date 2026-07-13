import { useEffect, useState, useCallback } from 'react'
import {
  Plug,
  Plus,
  Trash2,
  RefreshCw,
  Activity,
  Wrench,
  CheckCircle2,
  XCircle,
  Download,
  Loader2,
} from 'lucide-react'
import {
  Button,
  Input,
  Select,
  Switch,
  Badge,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  EmptyState,
  Modal,
} from '@/components/ui'
import { mcpApi } from '@/services/api'
import type { MCPServer, MCPServerCreate, MCPTransport, MCPServerHealthResponse } from '@/types/api'
import { toastError, toastSuccess } from '@/stores/toastStore'
import { useTranslation } from '@/i18n'

const transportOptions: Array<{ value: MCPTransport; label: string }> = [
  { value: 'embedded', label: 'Embedded' },
  { value: 'stdio', label: 'Stdio' },
  { value: 'sse', label: 'SSE' },
]

interface MCPFormState {
  id: string
  name: string
  description: string
  transport: MCPTransport
  package: string
  command: string
  args: string
  url: string
  env: string
  category: string
}

function defaultForm(): MCPFormState {
  return {
    id: '',
    name: '',
    description: '',
    transport: 'stdio',
    package: '',
    command: '',
    args: '',
    url: '',
    env: '',
    category: 'general',
  }
}

function parseArgs(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

function parseEnv(value: string): Record<string, string> {
  const env: Record<string, string> = {}
  value.split(',').forEach((part) => {
    const [k, ...rest] = part.split('=')
    if (k && rest.length > 0) {
      env[k.trim()] = rest.join('=').trim()
    }
  })
  return env
}

export function MCPMarketplace() {
  const { t } = useTranslation()
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(defaultForm())
  const [formError, setFormError] = useState<string | null>(null)
  const [healthResults, setHealthResults] = useState<Record<string, MCPServerHealthResponse>>({})
  const [pending, setPending] = useState<Record<string, string>>({})

  const fetchServers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await mcpApi.listServers()
      setServers(res.data)
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('mcp.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    fetchServers()
  }, [fetchServers])

  const setActionPending = (id: string, action: string | null) => {
    setPending((prev) => {
      const next = { ...prev }
      if (action) {
        next[id] = action
      } else {
        delete next[id]
      }
      return next
    })
  }

  const handleToggle = async (server: MCPServer) => {
    const action = server.enabled ? 'disable' : 'enable'
    setActionPending(server.id, action)
    try {
      if (server.enabled) {
        await mcpApi.disableServer(server.id)
        toastSuccess(`${server.name} ${t('mcp.disabled')}`)
      } else {
        await mcpApi.enableServer(server.id)
        toastSuccess(`${server.name} ${t('mcp.enabled')}`)
      }
      await fetchServers()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t(server.enabled ? 'mcp.disableFailed' : 'mcp.enableFailed'))
    } finally {
      setActionPending(server.id, null)
    }
  }

  const handleInstall = async (server: MCPServer) => {
    setActionPending(server.id, 'install')
    try {
      await mcpApi.installServer(server.id)
      toastSuccess(`${server.name} ${t('mcp.installed')}`)
      await fetchServers()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('mcp.installFailed'))
    } finally {
      setActionPending(server.id, null)
    }
  }

  const handleRemove = async (server: MCPServer) => {
    if (!confirm(t('mcp.removeConfirm', { name: server.name }))) return
    setActionPending(server.id, 'remove')
    try {
      await mcpApi.removeServer(server.id)
      toastSuccess(`${server.name} removed`)
      await fetchServers()
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('mcp.removeFailed'))
    } finally {
      setActionPending(server.id, null)
    }
  }

  const handleHealthCheck = async (server: MCPServer) => {
    setActionPending(server.id, 'health')
    try {
      const res = await mcpApi.healthCheck(server.id)
      setHealthResults((prev) => ({ ...prev, [server.id]: res.data }))
    } catch (err: any) {
      toastError(err?.response?.data?.detail || t('mcp.healthFailed'))
    } finally {
      setActionPending(server.id, null)
    }
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (!form.id.trim()) {
      setFormError(t('mcp.idRequired'))
      return
    }
    if (!form.name.trim()) {
      setFormError(t('mcp.nameRequired'))
      return
    }

    const payload: MCPServerCreate = {
      id: form.id.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      transport: form.transport,
      category: form.category.trim() || 'general',
      env: parseEnv(form.env),
    }

    if (form.transport === 'stdio') {
      if (form.package.trim()) {
        payload.package = form.package.trim()
      }
      if (form.command.trim()) {
        payload.command = form.command.trim()
        payload.args = parseArgs(form.args)
      }
    } else if (form.transport === 'sse') {
      payload.url = form.url.trim()
    }

    try {
      await mcpApi.addServer(payload)
      toastSuccess(`${payload.name} ${t('common.saved')}`)
      setShowAdd(false)
      setForm(defaultForm())
      await fetchServers()
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || t('mcp.addFailed'))
    }
  }

  const isPending = (server: MCPServer, action: string) => pending[server.id] === action

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background p-4">
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Plug className="h-7 w-7 text-primary" />
          <div>
            <h2 className="text-2xl font-bold text-foreground">{t('mcp.title')}</h2>
            <p className="text-sm text-muted-foreground">{t('mcp.subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchServers} disabled={loading}>
            <RefreshCw className={loading ? 'mr-1.5 h-4 w-4 animate-spin' : 'mr-1.5 h-4 w-4'} />
            {t('common.refresh')}
          </Button>
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            {t('mcp.addServer')}
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {servers.length === 0 && !loading ? (
          <EmptyState
            icon={Plug}
            title={t('mcp.empty')}
            description={t('mcp.emptyDesc')}
            action={{ label: t('mcp.addServer'), onClick: () => setShowAdd(true) }}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {servers.map((server) => {
              const health = healthResults[server.id]
              return (
                <Card key={server.id} className="flex flex-col transition-shadow hover:shadow-soft">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <CardTitle className="truncate text-base">{server.name}</CardTitle>
                        <CardDescription className="line-clamp-2">
                          {server.description || `${server.transport} • ${server.category}`}
                        </CardDescription>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        {server.builtin && <Badge variant="secondary" size="sm">{t('mcp.builtin')}</Badge>}
                        {server.enabled ? (
                          <Badge variant="success" size="sm">{t('mcp.enabled')}</Badge>
                        ) : (
                          <Badge variant="outline" size="sm">{t('mcp.disabled')}</Badge>
                        )}
                        {server.transport === 'stdio' && (
                          <Badge variant={server.installed ? 'success' : 'warning'} size="sm">
                            {server.installed ? t('mcp.installed') : t('mcp.notInstalled')}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="flex-1 space-y-3">
                    <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                      <Badge variant="outline" size="sm">{server.transport}</Badge>
                      <Badge variant="outline" size="sm">{server.category}</Badge>
                      {server.tools.length > 0 && (
                        <Badge variant="outline" size="sm">
                          <Wrench className="mr-1 h-3 w-3" />
                          {t('mcp.toolCount', { count: server.tools.length })}
                        </Badge>
                      )}
                    </div>

                    {server.package && (
                      <p className="text-xs text-muted-foreground">
                        {t('mcp.package')}: {server.package}
                      </p>
                    )}
                    {server.command && (
                      <p className="truncate text-xs text-muted-foreground">
                        {server.command} {server.args.join(' ')}
                      </p>
                    )}
                    {server.url && (
                      <p className="truncate text-xs text-muted-foreground">{server.url}</p>
                    )}

                    {server.install_status && !server.installed && (
                      <p className="text-xs text-error">{server.install_status}</p>
                    )}

                    {health && (
                      <div
                        className={`rounded-lg border px-3 py-2 text-xs ${
                          health.status === 'ok'
                            ? 'border-success/30 bg-success/10 text-success'
                            : 'border-error/30 bg-error/10 text-error'
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          {health.status === 'ok' ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5" />
                          )}
                          <span className="font-medium">
                            {health.status === 'ok'
                              ? t('mcp.toolCount', { count: health.tool_count })
                              : health.error}
                          </span>
                        </div>
                      </div>
                    )}
                  </CardContent>

                  <CardFooter className="flex-wrap justify-end gap-2 border-t border-border pt-4">
                    {!server.builtin && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRemove(server)}
                        disabled={isPending(server, 'remove')}
                      >
                        {isPending(server, 'remove') ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        {t('mcp.remove')}
                      </Button>
                    )}

                    {server.transport === 'stdio' && !server.installed && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleInstall(server)}
                        disabled={isPending(server, 'install')}
                      >
                        {isPending(server, 'install') ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        {t('mcp.install')}
                      </Button>
                    )}

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleHealthCheck(server)}
                      disabled={isPending(server, 'health')}
                    >
                      {isPending(server, 'health') ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Activity className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {t('mcp.healthCheck')}
                    </Button>

                    <Switch
                      checked={server.enabled}
                      onChange={() => handleToggle(server)}
                      disabled={isPending(server, 'enable') || isPending(server, 'disable')}
                      label={server.enabled ? t('mcp.enabled') : t('mcp.disabled')}
                    />
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      <Modal
        open={showAdd}
        onClose={() => {
          setShowAdd(false)
          setForm(defaultForm())
          setFormError(null)
        }}
        title={t('mcp.addServer')}
        description=""
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowAdd(false)
                setForm(defaultForm())
                setFormError(null)
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button onClick={handleAdd}>{t('common.save')}</Button>
          </div>
        }
      >
        <form id="mcp-add-form" onSubmit={handleAdd} className="space-y-4">
          {formError && (
            <div className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
              {formError}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">ID *</label>
              <Input
                value={form.id}
                onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                placeholder="my-server"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('mcp.name')} *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder={t('mcp.namePlaceholder')}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">{t('mcp.description')}</label>
            <Input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('mcp.transport')}</label>
              <Select
                value={form.transport}
                options={transportOptions}
                onChange={(e) => setForm((f) => ({ ...f, transport: e.target.value as MCPTransport }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('mcp.category')}</label>
              <Input
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              />
            </div>
          </div>

          {form.transport === 'stdio' && (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('mcp.package')}</label>
                <Input
                  value={form.package}
                  onChange={(e) => setForm((f) => ({ ...f, package: e.target.value }))}
                  placeholder={t('mcp.packagePlaceholder')}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('mcp.command')}</label>
                  <Input
                    value={form.command}
                    onChange={(e) => setForm((f) => ({ ...f, command: e.target.value }))}
                    placeholder={t('mcp.commandPlaceholder')}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t('mcp.args')}</label>
                  <Input
                    value={form.args}
                    onChange={(e) => setForm((f) => ({ ...f, args: e.target.value }))}
                    placeholder="arg1, arg2"
                  />
                </div>
              </div>
            </>
          )}

          {form.transport === 'sse' && (
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('mcp.url')}</label>
              <Input
                value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                placeholder={t('mcp.urlPlaceholder')}
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">ENV (KEY=VALUE, comma separated)</label>
            <Input
              value={form.env}
              onChange={(e) => setForm((f) => ({ ...f, env: e.target.value }))}
              placeholder="API_KEY=xyz, DEBUG=1"
            />
          </div>
        </form>
      </Modal>
    </div>
  )
}
