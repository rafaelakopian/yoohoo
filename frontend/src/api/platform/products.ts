import apiClient from '@/api/client'

export interface NavigationItemResponse {
  product: string
  label: string
  route_suffix: string
  icon: string
  permissions: string[]
  order: number
  active_paths: string[] | null
}

export interface ProductResponse {
  slug: string
  name: string
  description: string
  version: string
}

export interface ProductRegistryResponse {
  products: ProductResponse[]
  navigation: NavigationItemResponse[]
}

export async function getProductRegistry(): Promise<ProductRegistryResponse> {
  const { data } = await apiClient.get('/platform/products/registry')
  return data
}
