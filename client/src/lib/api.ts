import axios from 'axios';

// --- API CLIENT SETUP ---
const apiClient = axios.create({
  // FIX: Corrected the invalid IP address to the standard localhost loopback address.
  baseURL: 'http://127.0.0.1:8000', // Your FastAPI backend URL
});

// --- TYPE DEFINITION (API CONTRACT) ---
// This should match the data structure sent by your backend
export interface Task {
  id: string;
  filename: string;
  // Use a specific union type for status to enforce type safety
  status: 'processing' | 'completed' | 'failed';
  summary?: string;
  keyPoints?: string[];
  departmentSuggestion?: {
    department: string;
    confidence: number;
    reasoning: string;
  };
  // Timestamp is critical for sorting new uploads
  timestamp: string;
}

// --- API FUNCTIONS ---

/**
 * Fetches all tasks from the backend.
 */
export const getTasks = async (): Promise<Task[]> => {
  try {
    const response = await apiClient.get<Task[]>('/tasks');
    return response.data;
  } catch (error) {
    console.error("API Error: Failed to fetch tasks.", error);
    // Return an empty array on error to prevent the app from crashing
    return [];
  }
};

/**
 * Uploads one or more files to the backend.
 */
export const uploadFiles = async (files: File[]): Promise<void> => {
  const formData = new FormData();
  files.forEach(file => {
    // The key "files" must match the FastAPI endpoint parameter name
    formData.append("files", file); 
  });

  try {
    await apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  } catch (error) {
    console.error("API Error: Failed to upload files.", error);
    // Re-throw the error so the component can handle it
    throw error;
  }
};
