// API response types matching backend schemas

export interface ItemTags {
  colors: string[];
  primary_color?: string;
  pattern?: string;
  material?: string;
  style: string[];
  season: string[];
  formality?: string;
  fit?: string;
  occasion?: string[];
  brand?: string;
  condition?: string;
  features?: string[];
  logprobs_confidence?: number;
}

export interface Item {
  id: string;
  user_id: string;
  type: string;
  subtype?: string;
  name?: string;
  brand?: string;
  notes?: string;
  purchase_date?: string;
  purchase_price?: number;
  favorite: boolean;
  image_path: string;
  thumbnail_path?: string;
  medium_path?: string;
  image_url?: string;
  thumbnail_url?: string;
  medium_url?: string;
  tags: ItemTags;
  colors: string[];
  primary_color?: string;
  status: 'processing' | 'ready' | 'error' | 'archived';
  ai_processed: boolean;
  ai_confidence?: number;
  ai_description?: string;
  wear_count: number;
  last_worn_at?: string;
  last_suggested_at?: string;
  suggestion_count: number;
  acceptance_count: number;
  wears_since_wash: number;
  last_washed_at?: string;
  wash_interval?: number;
  needs_wash: boolean;
  effective_wash_interval: number;
  additional_images: ItemImage[];
  is_archived: boolean;
  archived_at?: string;
  archive_reason?: string;
  is_private: boolean;
  created_at: string;
  updated_at: string;
}

export interface ItemListResponse {
  items: Item[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ItemFilter {
  type?: string;
  subtype?: string;
  colors?: string[];
  status?: string;
  favorite?: boolean;
  needs_wash?: boolean;
  is_archived?: boolean;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  ids?: string;
  owner_scope?: 'mine' | 'family';
}

export interface StyleProfile {
  casual: number;
  formal: number;
  sporty: number;
  minimalist: number;
  bold: number;
}

export interface AIEndpoint {
  name: string;
  url: string;
  vision_model: string;
  text_model: string;
  enabled: boolean;
}

export interface Preferences {
  color_favorites: string[];
  color_avoid: string[];
  style_profile: StyleProfile;
  default_occasion: string;
  temperature_unit: 'celsius' | 'fahrenheit';
  temperature_sensitivity: 'low' | 'normal' | 'high';
  cold_threshold: number;
  hot_threshold: number;
  layering_preference: 'minimal' | 'moderate' | 'heavy';
  avoid_repeat_days: number;
  prefer_underused_items: boolean;
  variety_level: 'low' | 'moderate' | 'high';
  ai_endpoints: AIEndpoint[];
}

// Body-type styler profile types — GET/PUT /style-profile, POST /style-profile/draft,
// GET /style-profile/guidance. NOTE: named `StyleProfileData` (not `StyleProfile`) to avoid
// colliding with the pre-existing `StyleProfile` sliders type above (casual/formal/etc.,
// part of `Preferences.style_profile`) — these are two distinct concepts sharing a name
// upstream in the task brief.
export interface StyleProfileData {
  measurements: Record<string, unknown>;
  body_shape: string | null; // hourglass|pear|inverted-triangle|rectangle|apple
  vertical_line: string | null; // petite|balanced|tall
  frame: string | null; // small|medium|large
  color_season: string | null; // e.g. soft-autumn, cool-winter
  kibbe_lean: string | null; // dramatic|natural|romantic|classic|gamine
  palette: string[];
  season_confirmed: boolean;
  kibbe_confirmed: boolean;
}

// PUT /style-profile body — mirrors backend's StyleProfileUpdate (all fields optional)
export interface StyleProfileUpdate {
  color_season?: string | null;
  kibbe_lean?: string | null;
  palette?: string[];
  season_confirmed?: boolean;
  kibbe_confirmed?: boolean;
}

// POST /style-profile/draft body — mirrors backend's StyleDraftRequest
export interface StyleDraftRequest {
  hints?: Record<string, unknown>;
  image_b64?: string;
}

// POST /style-profile/draft response — advisory, unsaved AI guess
export interface StyleDraft {
  color_season: string | null;
  kibbe_lean: string | null;
}

// GET /style-profile/guidance response
export interface Guidance {
  summary: string;
  recommended: Record<string, string[]>;
  avoid: Record<string, string[]>;
  palette: string[];
}

// Color options for the app
// Hex values tuned for typical clothing colors, not pure/saturated colors
export const CLOTHING_COLORS = [
  { name: 'Black', value: 'black', hex: '#1a1a1a' },
  { name: 'Charcoal', value: 'charcoal', hex: '#36454F' },
  { name: 'Gray', value: 'gray', hex: '#808080' },
  { name: 'White', value: 'white', hex: '#FAFAFA' },
  { name: 'Cream', value: 'cream', hex: '#F5F5DC' },
  { name: 'Beige', value: 'beige', hex: '#D4C4A8' },
  { name: 'Tan', value: 'tan', hex: '#C9B896' },
  { name: 'Khaki', value: 'khaki', hex: '#A89F6B' },
  { name: 'Olive', value: 'olive', hex: '#707B52' },
  { name: 'Army Green', value: 'army-green', hex: '#5B6340' },
  { name: 'Green', value: 'green', hex: '#4A7C59' },
  { name: 'Teal', value: 'teal', hex: '#367588' },
  { name: 'Navy', value: 'navy', hex: '#1B2A4A' },
  { name: 'Blue', value: 'blue', hex: '#4A7DB8' },
  { name: 'Brown', value: 'brown', hex: '#8B5A3C' },
  { name: 'Dark Brown', value: 'dark-brown', hex: '#5C4033' },
  { name: 'Burgundy', value: 'burgundy', hex: '#722F37' },
  { name: 'Red', value: 'red', hex: '#C44536' },
  { name: 'Pink', value: 'pink', hex: '#E8A0B0' },
  { name: 'Purple', value: 'purple', hex: '#6B5B7A' },
  { name: 'Yellow', value: 'yellow', hex: '#D4A84B' },
  { name: 'Orange', value: 'orange', hex: '#D2691E' },
] as const;

// Clothing types — must match the TYPE vocabulary in clothing_analysis.txt
export const CLOTHING_TYPES = [
  { label: 'Shirt', value: 'shirt' },
  { label: 'T-Shirt', value: 't-shirt' },
  { label: 'Top', value: 'top' },
  { label: 'Polo', value: 'polo' },
  { label: 'Blouse', value: 'blouse' },
  { label: 'Tank Top', value: 'tank-top' },
  { label: 'Sweater', value: 'sweater' },
  { label: 'Hoodie', value: 'hoodie' },
  { label: 'Cardigan', value: 'cardigan' },
  { label: 'Vest', value: 'vest' },
  { label: 'Pants', value: 'pants' },
  { label: 'Jeans', value: 'jeans' },
  { label: 'Shorts', value: 'shorts' },
  { label: 'Skirt', value: 'skirt' },
  { label: 'Dress', value: 'dress' },
  { label: 'Jumpsuit', value: 'jumpsuit' },
  { label: 'Jacket', value: 'jacket' },
  { label: 'Blazer', value: 'blazer' },
  { label: 'Coat', value: 'coat' },
  { label: 'Suit', value: 'suit' },
  { label: 'Shoes', value: 'shoes' },
  { label: 'Sneakers', value: 'sneakers' },
  { label: 'Boots', value: 'boots' },
  { label: 'Sandals', value: 'sandals' },
  { label: 'Socks', value: 'socks' },
  { label: 'Tie', value: 'tie' },
  { label: 'Hat', value: 'hat' },
  { label: 'Scarf', value: 'scarf' },
  { label: 'Belt', value: 'belt' },
  { label: 'Bag', value: 'bag' },
  { label: 'Jewelry', value: 'jewelry' },
  { label: 'Watch', value: 'watch' },
  { label: 'Sunglasses', value: 'sunglasses' },
  { label: 'Gloves', value: 'gloves' },
  { label: 'Accessories', value: 'accessories' },
  { label: 'Bra', value: 'bra' },
  { label: 'Sports Bra', value: 'sports-bra' },
  { label: 'Underwear', value: 'underwear' },
  { label: 'Briefs', value: 'briefs' },
  { label: 'Boxers', value: 'boxers' },
  { label: 'Lingerie', value: 'lingerie' },
  { label: 'Shapewear', value: 'shapewear' },
  { label: 'Tights', value: 'tights' },
  { label: 'Pajamas', value: 'pajamas' },
  { label: 'Robe', value: 'robe' },
  { label: 'Swimwear', value: 'swimwear' },
  { label: 'Leggings', value: 'leggings' },
  { label: 'Gym Top', value: 'gym-top' },
  { label: 'Joggers', value: 'joggers' },
  { label: 'Tracksuit', value: 'tracksuit' },
  { label: 'Base Layer', value: 'base-layer' },
] as const;

// Taxonomy types — category > type > subtype hierarchy served by GET /api/v1/taxonomy
export interface TaxonomyType {
  type: string;
  subtypes: string[];
}

export interface TaxonomyCategory {
  category: string;
  types: TaxonomyType[];
}

export interface Taxonomy {
  categories: TaxonomyCategory[];
}

export const OCCASIONS = [
  { label: 'Casual', value: 'casual' },
  { label: 'Office', value: 'office' },
  { label: 'Formal', value: 'formal' },
  { label: 'Date', value: 'date' },
  { label: 'Sporty', value: 'sporty' },
  { label: 'Outdoor', value: 'outdoor' },
] as const;

// Family types
export interface FamilyMember {
  id: string;
  display_name: string;
  email: string;
  avatar_url?: string;
  role: 'admin' | 'member';
  created_at: string;  // When user joined the family
}

export interface PendingInvite {
  id: string;
  email: string;
  created_at: string;  // When invite was sent
  expires_at: string;
}

export interface Family {
  id: string;
  name: string;
  invite_code: string;
  members: FamilyMember[];
  pending_invites: PendingInvite[];
  created_at: string;
}

export interface FamilyCreateResponse {
  id: string;
  name: string;
  invite_code: string;
  role: string;
}

export interface JoinFamilyResponse {
  family_id: string;
  family_name: string;
  role: string;
}

// Multi-image types
export interface ItemImage {
  id: string;
  item_id: string;
  image_path: string;
  thumbnail_path?: string;
  medium_path?: string;
  position: number;
  created_at: string;
  image_url: string;
  thumbnail_url?: string;
  medium_url?: string;
}

// Wash tracking types
export interface WashHistoryEntry {
  id: string;
  item_id: string;
  washed_at: string;
  method?: string;
  notes?: string;
  created_at: string;
}

// Family rating types
export interface FamilyRating {
  id: string;
  user_id: string;
  user_display_name: string;
  user_avatar_url?: string;
  rating: number;
  comment?: string;
  created_at: string;
}

// Outfit types
export interface OutfitItem {
  id: string;
  type: string;
  subtype?: string;
  name?: string;
  primary_color?: string;
  colors: string[];
  image_path: string;
  thumbnail_path?: string;
  image_url?: string;
  thumbnail_url?: string;
  layer_type?: string;
  position: number;
}

export interface WeatherData {
  temperature: number;
  feels_like: number;
  humidity: number;
  precipitation_chance: number;
  condition: string;
}

export interface FeedbackSummary {
  rating?: number;
  comment?: string;
  worn_at?: string;
}

export type OutfitSource = 'scheduled' | 'on_demand' | 'manual' | 'pairing';

export interface Outfit {
  id: string;
  occasion: string;
  scheduled_for: string;
  status: 'pending' | 'sent' | 'viewed' | 'accepted' | 'rejected' | 'expired';
  source: OutfitSource;
  reasoning?: string;
  style_notes?: string;
  highlights?: string[];
  weather?: WeatherData;
  items: OutfitItem[];
  feedback?: FeedbackSummary;
  family_ratings?: FamilyRating[];
  family_rating_average?: number;
  family_rating_count?: number;
  created_at: string;
}

export interface SuggestRequest {
  occasion: string;
  weather_override?: {
    temperature: number;
    feels_like?: number;
    humidity: number;
    precipitation_chance: number;
    condition: string;
  };
  exclude_items?: string[];
  include_items?: string[];
}

// Pairing types
export interface SourceItem {
  id: string;
  type: string;
  subtype?: string;
  name?: string;
  primary_color?: string;
  image_path: string;
  thumbnail_path?: string;
  image_url?: string;
  thumbnail_url?: string;
}

export interface Pairing extends Outfit {
  source_item?: SourceItem;
}

export interface PairingListResponse {
  pairings: Pairing[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface GeneratePairingsRequest {
  num_pairings: number;
}

export interface GeneratePairingsResponse {
  generated: number;
  pairings: Pairing[];
}

// Calendar types
export interface OutfitBrief {
  id: string;
  occasion: string;
  scheduled_for: string | null;
  worn_at: string | null;
  name: string | null;
  item_ids: string[];
}

export interface DayRecord {
  date: string;
  primary: OutfitBrief | null;
  extras: OutfitBrief[];
  repeat_warnings?: string[];
}

// Buy-Advisor types — GET /buy-advisor, POST /buy-advisor/size
export interface BuySearchLink {
  retailer: string;
  url: string;
}

export interface BuyRec {
  role: string;
  type: string;
  silhouette: string | null;
  color: string | null;
  rationale: string;
  search_links: BuySearchLink[];
}

export interface BuyAdvisorResponse {
  recommendations: BuyRec[];
}

// POST /buy-advisor/size body
export interface SizeForUrlRequest {
  product_url: string;
  product_type?: string;
}

// POST /buy-advisor/size response
export interface SizeResult {
  size: string;
  confidence: string;
  source: string;
}
