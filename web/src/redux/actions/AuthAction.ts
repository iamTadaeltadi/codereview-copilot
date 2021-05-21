import { createAsyncThunk } from '@reduxjs/toolkit';
import { login } from '../../api/AuthApi';
import type { AuthResponse, LoginPayload } from '../../api/AuthApi';

export const loginUser = createAsyncThunk<AuthResponse, LoginPayload>(
  'auth/loginUser',
  async (payload) => {
    const response = await login(payload);
    localStorage.setItem('authUser', JSON.stringify(response));
    return response;
  }
);
