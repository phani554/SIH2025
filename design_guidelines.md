# Design Guidelines for AI-Native Application Hub

## Design Decision Framework Analysis

**Selected Approach: Reference-Based (ChatGPT/Claude Interface)**
- **Justification**: Experience-focused AI interaction tool requiring intuitive conversational UI
- **Primary Reference**: ChatGPT and Claude interfaces for clean conversation flows
- **Key Principles**: Conversational clarity, real-time feedback, minimal cognitive load

## Core Design Elements

### A. Color Palette
**Dark Theme Implementation:**
- **Primary**: #6366F1 (Indigo) - buttons, active states, brand elements
- **Secondary**: #8B5CF6 (Purple) - accents, highlights, secondary actions
- **Background**: #1F2937 (Dark Grey) - main application background
- **Chat Background**: #111827 (Darker Grey) - chat message container
- **User Messages**: #6366F1 with white text
- **AI Messages**: #374151 (Medium Grey) with light text
- **Text Primary**: #F9FAFB (Light Grey) - main content text
- **Text Secondary**: #9CA3AF (Medium Grey) - secondary text, timestamps
- **Success**: #10B981 (Green) - file processing completion indicators
- **Border**: #374151 (Medium Grey) - panel separators, card borders

### B. Typography
- **Primary Font**: Inter (web font via Google Fonts CDN)
- **Fallback**: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
- **Message Text**: 14px/1.5 (readable conversation text)
- **UI Labels**: 12px/1.4 (form labels, status text)
- **Panel Titles**: 16px/1.3, font-weight: 600

### C. Layout System
**Tailwind Spacing Primitives**: 2, 4, 6, 8, 12, 16
- **Panel Gaps**: gap-4 (16px between panels)
- **Card Padding**: p-6 (24px internal spacing)
- **Message Spacing**: mb-4 (16px between messages)
- **Component Margins**: m-2, m-4 for consistent spacing

### D. Component Library

**Three-Panel Dashboard Layout:**
- **Left Sidebar**: 25% width, fixed position
  - File upload drag-drop zone with hover state changes
  - Processed documents list with scroll area
  - Green checkmark icons for completed files

**Center Chat Panel**: 50% width
- Message bubbles with 12px border radius
- User messages: right-aligned, indigo background
- AI messages: left-aligned, grey background with avatar
- Typing indicators with animated dots
- Message input with send button (disabled until first file processed)

**Right Context Panel**: 25% width
- Initially empty with placeholder text
- Future: document snippets and processing details

**Core UI Elements:**
- **Cards**: Shadcn Card components with dark theme
- **Buttons**: Primary (indigo), secondary (outline), icon-only for actions
- **Drag-Drop Zone**: Visual feedback on hover/drag-over states
- **ScrollAreas**: For chat history and file lists
- **Avatars**: User and AI conversation participants
- **Loading States**: Subtle animations for processing feedback

### E. Interactions & States
- **File Upload**: Visual feedback during drag operations
- **Chat Input**: Smooth enable/disable transitions
- **Message Streaming**: Real-time text appearance
- **Processing Status**: Clear visual indicators for file analysis
- **Responsive Behavior**: Mobile-first approach with panel stacking

## Visual Hierarchy
1. **Chat Messages**: Primary focus with clear user/AI distinction
2. **File Upload Zone**: Prominent placement for key workflow entry
3. **Processing Status**: Clear but non-intrusive completion indicators
4. **Context Panel**: Supporting information without distraction

## Key Design Patterns
- **Conversation Flow**: Clean message threading with clear attribution
- **Status Communication**: Immediate feedback for all user actions
- **Progressive Disclosure**: Context panel reveals relevant information
- **Accessibility**: High contrast ratios maintained in dark theme
- **Mobile Responsiveness**: Panel collapse/stack on smaller screens