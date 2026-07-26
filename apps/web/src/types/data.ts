/**
 * Data Model Types for API endpoints and items
 */

export interface ApiEndpoints {
  test: string;
  ping: string;
  echo: string;
  getAllData: string;
  filterData: string;
  getById: string;
}

export interface ApiWelcomeResponse {
  message: string;
  endpoints: ApiEndpoints;
}

export interface DataItem {
  id: number;
  name: string;
  category: string;
  price: number;
  status: 'active' | 'inactive' | 'pending' | string;
}

export interface SingleItemResponse {
  status: string;
  data: DataItem;
}

export interface ChatSession {
  id: string | number;
  title: string;
  category?: string;
  date?: string;
}
