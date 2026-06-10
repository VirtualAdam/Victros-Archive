/**
 * API client tests — mock fetch and verify the client sends correct
 * method, path, and body for each endpoint.
 */
import { api } from '../../api/client'

function mockFetch(data: unknown, status = 200) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  }))
}

afterEach(() => vi.restoreAllMocks())

describe('api.createSession', () => {
  it('POSTs to /api/session/create', async () => {
    mockFetch({ session_id: 'abc', state: 'NEW_SESSION' })
    await api.createSession({ user_id: 'u1', opportunity_id: 'opp1' })
    expect(fetch).toHaveBeenCalledWith(
      '/api/session/create',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('api.getSession', () => {
  it('GETs /api/session/:id', async () => {
    mockFetch({ session_id: 'abc', state: 'INTAKE' })
    await api.getSession('abc')
    expect(fetch).toHaveBeenCalledWith(
      '/api/session/abc',
      expect.objectContaining({}),
    )
  })
})

describe('api.submitInput', () => {
  it('POSTs button signals to /api/session/:id/input', async () => {
    mockFetch({ state: 'AWAITING_CONFIRMATION', proposal: null })
    await api.submitInput('s1', {
      input_type: 'button',
      signals: ['single_threaded_contact'],
    })
    const [url, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/session/s1/input')
    expect(opts.method).toBe('POST')
    const body = JSON.parse(opts.body)
    expect(body.signals).toContain('single_threaded_contact')
  })
})

describe('api.confirm', () => {
  it('POSTs confirm to /api/session/:id/confirm', async () => {
    mockFetch({ state: 'PRESENTING_DIAGNOSIS' })
    await api.confirm('s1', { response: 'confirm', deal_stage: '3_Validation' })
    const [url, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/session/s1/confirm')
    const body = JSON.parse(opts.body)
    expect(body.response).toBe('confirm')
    expect(body.deal_stage).toBe('3_Validation')
  })
})

describe('api.selectAction', () => {
  it('POSTs to /api/session/:id/select-action', async () => {
    mockFetch({ state: 'MONITORING', action_key: 'run_action' })
    await api.selectAction('s1', { action_key: 'run_action' })
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/session/s1/select-action')
  })
})

describe('api error handling', () => {
  it('throws on non-2xx response', async () => {
    mockFetch({ detail: 'Not found' }, 404)
    await expect(api.getSession('missing')).rejects.toThrow('404')
  })
})
