import { Users } from 'lucide-react'
import type { PresenceUser } from '@/api/collab'

interface ActiveUsersProps {
  users: PresenceUser[]
  isConnected: boolean
}

export function ActiveUsers({ users, isConnected }: ActiveUsersProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
      <Users size={16} />
      <span>{isConnected ? 'Live' : 'Offline'}</span>
      {users.length > 0 && (
        <div className="flex -space-x-1.5">
          {users.slice(0, 5).map((user) => (
            <div
              key={user.user_id}
              className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-medium text-white ring-2 ring-white dark:ring-slate-900"
              style={{ backgroundColor: user.color || '#64748b' }}
              title={user.user_id}
            >
              {user.user_id.slice(0, 2).toUpperCase()}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
