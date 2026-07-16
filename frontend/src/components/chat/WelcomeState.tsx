import { clsx } from 'clsx'
import { useTranslation } from '@/i18n'
import { Dna, Microscope, BrainCircuit, FlaskConical } from 'lucide-react'

const capabilities = [
  { key: 'chat.welcomeCapability1', icon: Dna },
  { key: 'chat.welcomeCapability2', icon: Microscope },
  { key: 'chat.welcomeCapability3', icon: BrainCircuit },
  { key: 'chat.welcomeCapability4', icon: FlaskConical },
]

export function WelcomeState({ className }: { className?: string }) {
  const { t } = useTranslation()

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center p-8 text-center',
        className
      )}
    >
      <div className="relative mb-6">
        <div className="h-20 w-20 overflow-hidden rounded-2xl border border-border-faint bg-surface shadow-sm">
          <img
            src="/homomics-logo.png"
            alt="HomomicsLab"
            className="h-full w-full object-contain"
          />
        </div>
        <div className="absolute -bottom-1.5 -right-1.5 rounded-full border-2 border-background bg-accent px-2 py-0.5 text-[10px] font-semibold text-accent-foreground shadow-sm">
          AI
        </div>
      </div>

      <h1 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
        {t('chat.welcomeTitle')}
      </h1>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        {t('chat.welcomeSubtitle')}
      </p>

      <div className="mt-8 grid w-full max-w-lg grid-cols-1 gap-3 sm:grid-cols-2">
        {capabilities.map(({ key, icon: Icon }) => (
          <div
            key={key}
            className="flex items-center gap-3 rounded-xl border border-border-faint bg-surface/50 p-3 text-left transition-colors hover:bg-surface"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <Icon className="h-4 w-4" />
            </div>
            <span className="text-xs font-medium text-foreground">{t(key)}</span>
          </div>
        ))}
      </div>

      <p className="mt-8 text-xs text-muted-foreground/70">
        {t('chat.welcomeHint')}
      </p>
    </div>
  )
}
