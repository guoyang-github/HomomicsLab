import type { PresenceUser } from '@/api/collab'

interface PresenceCursorsProps {
  users: PresenceUser[]
}

export function PresenceCursors({ users }: PresenceCursorsProps) {
  return (
    <>
      {users.map((user) =>
        user.cursor_x == null || user.cursor_y == null ? null : (
          <div
            key={user.user_id}
            className="pointer-events-none fixed z-50 flex items-center gap-1 transition-all duration-75"
            style={{
              left: user.cursor_x,
              top: user.cursor_y,
            }}
          >
            <svg
              width="20"
              height="24"
              viewBox="0 0 20 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ color: user.color || '#64748b' }}
            >
              <path
                d="M2.5 2L17.5 12.5L10 14L6.5 21.5L2.5 2Z"
                fill="currentColor"
                stroke="white"
                strokeWidth="1.5"
              />
            </svg>
            <span
              className="rounded px-1.5 py-0.5 text-xs text-white shadow"
              style={{ backgroundColor: user.color || '#64748b' }}
            >
              {user.user_id}
            </span>
          </div>
        )
      )}
    </>
  )
}
