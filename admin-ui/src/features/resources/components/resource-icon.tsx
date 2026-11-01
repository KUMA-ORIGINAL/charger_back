import {
  Activity,
  ArrowLeftRight,
  Boxes,
  Building2,
  Coins,
  Copy,
  CreditCard,
  DoorOpen,
  Eye,
  EyeOff,
  FileUp,
  FolderTree,
  History,
  Image,
  Languages,
  type LucideIcon,
  type LucideProps,
  Package,
  PackagePlus,
  Percent,
  QrCode,
  Receipt,
  ReceiptText,
  Refrigerator,
  RotateCcw,
  ScrollText,
  ShoppingCart,
  Table2,
  Ticket,
  UserCog,
  Users,
} from 'lucide-react'

/**
 * Иконки по имени из /meta/ (`icon = "package"` в StaffResource). Список
 * явный, чтобы не тянуть в бандл весь lucide; новое имя — добавить сюда.
 */
const ICONS: Record<string, LucideIcon> = {
  activity: Activity,
  'arrow-left-right': ArrowLeftRight,
  boxes: Boxes,
  'building-2': Building2,
  coins: Coins,
  copy: Copy,
  'credit-card': CreditCard,
  'door-open': DoorOpen,
  eye: Eye,
  'eye-off': EyeOff,
  'file-up': FileUp,
  'folder-tree': FolderTree,
  history: History,
  image: Image,
  languages: Languages,
  package: Package,
  'package-plus': PackagePlus,
  percent: Percent,
  'qr-code': QrCode,
  receipt: Receipt,
  'receipt-text': ReceiptText,
  refrigerator: Refrigerator,
  'rotate-ccw': RotateCcw,
  'scroll-text': ScrollText,
  'shopping-cart': ShoppingCart,
  table: Table2,
  ticket: Ticket,
  'user-cog': UserCog,
  users: Users,
}

export function ResourceIcon({ name, ...props }: { name: string } & LucideProps) {
  const Icon = ICONS[name] ?? Table2
  return <Icon {...props} />
}
