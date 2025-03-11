import { getApiClient } from './client';

export interface Goal {
  name: string;
  strategy?: string;
  description?: string;
  end_condition?: string;
  time_to_completion?: string;
  priority?: number;
  status_updates?: string[];
  created_at: string;
  completed_at?: string;
  is_active: boolean;
}

export interface GoalCreate {
  goal_name: string;
  strategy?: string;
  description?: string;
  end_condition?: string;
  time_to_completion?: string;
  priority?: number;
}

export interface GoalStatusUpdate {
  goal_name: string;
  status_update_or_note: string;
}

export interface GoalComplete {
  goal_name: string;
  closing_comments?: string;
}

export const GoalsApi = {
  getActiveGoals: async (): Promise<string[]> => {
    return getApiClient().get<string[]>('/goals');
  },

  getGoalByName: async (goalName: string): Promise<string> => {
    return getApiClient().get<string>(`/goals/${goalName}`);
  },

  createGoal: async (goal: GoalCreate): Promise<string> => {
    return getApiClient().post<string>('/goals', goal);
  },

  addStatusUpdate: async (goalName: string, update: GoalStatusUpdate): Promise<string> => {
    return getApiClient().post<string>(`/goals/${goalName}/status`, update);
  },

  completeGoal: async (goalName: string, complete: GoalComplete): Promise<string> => {
    return getApiClient().post<string>(`/goals/${goalName}/complete`, complete);
  }
};
