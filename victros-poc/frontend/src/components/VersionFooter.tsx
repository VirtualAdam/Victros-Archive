import { useEffect, useState } from 'react'

const UI_VERSION = 'D'

export function VersionFooter() {
  const [apiVersion, setApiVersion] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/version')
      .then((r) => r.json())
      .then((data) => setApiVersion(data.version))
      .catch(() => setApiVersion('?'))
  }, [])

  return (
    <footer className="fixed bottom-0 right-0 p-2 text-[10px] text-slate-600 select-none">
      {`UI:${UI_VERSION} | API:${apiVersion ?? '...'}`}
    </footer>
  )
}
