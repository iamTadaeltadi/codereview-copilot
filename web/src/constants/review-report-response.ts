export const  reviewReport = {
    "review": {
      "syntax": [
        {
          "issues": []
        },
        {
          "issues": []
        },
        {
          "issues": [
            {
              "location": "line 119",
              "file": "networks/factory.py",
              "description": "The 'if not (self.policy_nets and self.target_nets)' condition is the opposite of the original logic, this might be a logical error."
            }
          ]
        },
        {
          "issues": [
            {
              "location": "line 105",
              "file": "networks/inputs.py",
              "description": "The function __init__ should not contain a bare return statement without a value. In Python, the __init__ method should not return anything (or return None)."
            }
          ]
        },
        {
          "issues": []
        }
      ],
      "standards": [
        {
          "issues": [
            {
              "location": "line 83",
              "file": "agents/training.py",
              "standard": "Function name should be in camelCase, but 'reset_target_network' is in snake_case"
            },
            {
              "location": "line 88",
              "file": "agents/training.py",
              "standard": "Function name should be in camelCase, but 'train_batch' is in snake_case"
            },
            {
              "location": "line 84",
              "file": "agents/training.py",
              "standard": "Variable name 'self.config' seems to be accessing a potential constant or class, consider using uppercase or PascalCase"
            }
          ]
        },
        {
          "issues": [
            {
              "location": "line 45 and line 48",
              "file": "atari/atari.py",
              "standard": "Variable names should be in snake_case. 'self.frames' and 'self.input_frames', 'self.max_noops' are not following this convention if they are not defined elsewhere in the code. However, 'self.render' and 'self.env' seem to be following the convention."
            },
            {
              "location": "line 46 and line 48",
              "file": "atari/atari.py",
              "standard": "Function names should be in camelCase. 'self.env.render' and 'self.env.step' seem to be following this convention."
            },
            {
              "location": "Not enough information",
              "file": "Not enough information",
              "standard": "Class names should be in PascalCase. There is not enough information to determine if class names are being used correctly."
            },
