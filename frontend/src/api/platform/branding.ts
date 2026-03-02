import axios from 'axios'

export interface PlatformBranding {
  platform_name: string
  platform_name_short: string
  platform_url: string
}

export async function fetchBranding(): Promise<PlatformBranding> {
  const { data } = await axios.get<PlatformBranding>('/branding')
  return data
}
