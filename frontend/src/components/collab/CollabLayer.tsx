import { useEffect, useRef } from 'react'
import { usePresence } from '@/api/collab'
import { PresenceCursors } from './PresenceCursors'
import { useProjectStore } from '@/stores/projectStore'

const THROTTLE_MS = 80

export function CollabLayer() {
  const projectId = useProjectStore((state) => state.currentProjectId)
  const { users, sendCursor } = usePresence(
    projectId === 'default' ? null : projectId,
    'me'
  )
  const lastSentRef = useRef(0)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const now = Date.now()
      if (now - lastSentRef.current < THROTTLE_MS) {
        return
      }
      lastSentRef.current = now
      sendCursor(e.clientX, e.clientY)
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [sendCursor])

  // The collaboration badge in the bottom-right corner is intentionally removed.
  // A persistent "Offline" label is distracting and collides with the LLM status
  // indicator in the sidebar. Cursors still render when multi-user collaboration
  // is active.
  return <PresenceCursors users={users} />
}
