# 图标资源说明

本目录存放项目中使用的图标文件。

## 图标列表

### 1. 菜单图标
- **menu-expand.png** - 菜单展开时显示的图标（向左箭头 + 横线）
- **menu-collapse.png** - 菜单折叠时显示的图标（横线）

### 2. 功能图标
- **send.png** - 发送消息图标（纸飞机）
- **upload.png** - 上传文件图标（回形针）

## 使用方式

在 Vue 组件中导入并使用：

```vue
<script setup>
import menuExpandIcon from '@/assets/icons/menu-expand.png'
import menuCollapseIcon from '@/assets/icons/menu-collapse.png'
import sendIcon from '@/assets/icons/send.png'
import uploadIcon from '@/assets/icons/upload.png'
</script>

<template>
  <img :src="menuExpandIcon" alt="菜单" />
</template>
```

## 图标规格

- 格式：PNG
- 尺寸：根据实际使用场景调整
- 颜色：可通过 CSS filter 调整

## CSS 样式示例

```css
/* 调整图标大小 */
.icon {
  width: 24px;
  height: 24px;
}

/* 折叠状态下图标变白色 */
.collapsed .icon {
  filter: brightness(0) invert(1);
}

/* 调整图标透明度 */
.icon {
  opacity: 0.6;
}

.icon:hover {
  opacity: 1;
}
```

## 更新日期

2025-11-21

