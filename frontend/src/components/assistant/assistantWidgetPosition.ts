export const ASSISTANT_BUTTON_SIZE = 56;
export const ASSISTANT_EDGE_MARGIN = 12;
export const ASSISTANT_DRAG_THRESHOLD = 6;

export interface AssistantPosition { x: number; y: number }

export function assistantPositionStorageKey(userId: string) {
  return `comptaflow_assistant_position_${userId}`;
}

export function clampAssistantPosition(position: AssistantPosition, width: number, height: number): AssistantPosition {
  return {
    x: Math.min(
      Math.max(position.x, ASSISTANT_EDGE_MARGIN),
      Math.max(ASSISTANT_EDGE_MARGIN, width - ASSISTANT_BUTTON_SIZE - ASSISTANT_EDGE_MARGIN),
    ),
    y: Math.min(
      Math.max(position.y, ASSISTANT_EDGE_MARGIN),
      Math.max(ASSISTANT_EDGE_MARGIN, height - ASSISTANT_BUTTON_SIZE - ASSISTANT_EDGE_MARGIN),
    ),
  };
}
