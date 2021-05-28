// src/redux/slices/AuthSlice.ts
import { createSlice } from '@reduxjs/toolkit';
import { loginUser } from '../actions/AuthAction';
import type { AuthResponse } from '../../api/AuthApi';

interface AuthState {
  user: AuthResponse['user'] | null;
  token: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  token: null,
  loading: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state) {
      state.user = null;
      state.token = null;
      localStorage.removeItem('authUser');
    },
    restoreAuth(state) {
      const data = localStorage.getItem('authUser');
      if (data) {
        try {
          const parsed = JSON.parse(data);
          state.user = parsed.user;
          state.token = parsed.token;
        } catch (e) {
          console.error('Failed to parse authUser:', e);
        }
      }
    },
  },
  extraReducers: (builder) => {
    builder

      .addCase(loginUser.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.token = action.payload.token;
        localStorage.setItem('authUser', JSON.stringify(action.payload));
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Login failed';
      });
  },
});

export const { logout, restoreAuth } = authSlice.actions;
export default authSlice.reducer;
