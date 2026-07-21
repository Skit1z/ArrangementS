/**
 * 全站统一设计 Token —— 国内严谨简约风格
 *
 * 设计原则：
 * - 中性色为主，去除渐变与高饱和装饰
 * - 单一强调色（深青蓝），仅用于关键信息与可点击元素
 * - 统一的字号阶梯、间距与圆角，保证视觉层次清晰
 */

export const colors = {
  /** 主强调色：深青蓝（沉稳、严谨），用于当前状态、链接、关键操作 */
  primary: "#0F4C81",
  /** 主色浅底：当前班卡片背景等 */
  primaryBg: "#F0F5FA",
  /** 主色边框 */
  primaryBorder: "#C9D9E8",

  /** 正文主文字 */
  textPrimary: "#1F2329",
  /** 次级文字 */
  textSecondary: "#646A73",
  /** 辅助/说明文字 */
  textTertiary: "#8F959E",
  /** 占位/禁用文字 */
  textQuaternary: "#BBBFC4",

  /** 分割线/边框 */
  border: "#E5E6EB",
  /** 浅边框（卡片内分隔） */
  borderLight: "#EFF0F1",

  /** 页面背景 */
  bgPage: "#F5F6F7",
  /** 卡片/容器背景 */
  bgContainer: "#FFFFFF",
  /** 次级填充（上一班/下一班卡片背景） */
  bgFill: "#F7F8FA",

  /** 在岗状态绿（仅小面积状态点使用） */
  success: "#34A853",
} as const;

export const fontSize = {
  /** 页面级大数字/时间 */
  display: 20,
  /** 卡片标题 */
  title: 15,
  /** 正文强调 */
  bodyStrong: 14,
  /** 正文 */
  body: 13,
  /** 辅助说明 */
  caption: 12,
} as const;

export const radius = {
  card: 8,
  inner: 6,
} as const;

/** 统一卡片阴影：极浅，仅用于浮层区分 */
export const cardShadow = "0 1px 2px rgba(31, 35, 41, 0.04)" as const;

/** antd ConfigProvider 全局主题 */
export const antdTheme = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.primary,
    colorText: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorTextTertiary: colors.textTertiary,
    colorTextQuaternary: colors.textQuaternary,
    colorBorder: colors.border,
    colorBorderSecondary: colors.borderLight,
    colorBgLayout: colors.bgPage,
    colorBgContainer: colors.bgContainer,
    colorFillSecondary: colors.bgFill,
    borderRadius: radius.inner,
    fontSize: fontSize.body,
    // 统一行高，排版更规整
    lineHeight: 1.5715,
    // 去除默认蓝色阴影，按钮聚焦更克制
    controlOutlineWidth: 1,
  },
  components: {
    Card: {
      borderRadiusLG: radius.card,
      boxShadowTertiary: cardShadow,
      paddingLG: 20,
    },
    Button: {
      borderRadius: radius.inner,
      controlHeight: 34,
    },
    Table: {
      headerBg: colors.bgFill,
      headerColor: colors.textSecondary,
      borderColor: colors.borderLight,
    },
    Menu: {
      itemBorderRadius: radius.inner,
    },
    Layout: {
      bodyBg: colors.bgPage,
      headerBg: colors.bgContainer,
      siderBg: colors.bgContainer,
    },
  },
} as const;
