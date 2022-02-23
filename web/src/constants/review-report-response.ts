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
            {
              "location": "line 47",
              "file": "atari/atari.py",
              "standard": "The variable '_'' is not descriptive. While '_' is often used as a throwaway variable in Python, it's worth noting that using more descriptive variable names can improve code readability."
            },
            {
              "location": "Not enough information",
              "file": "Not enough information",
              "standard": "Constants should be in uppercase. There is not enough information to determine if constants are being used correctly."
            }
          ]
        },
        {
          "issues": [
            {
              "location": "line 121-124",
              "file": "networks/factory.py",
              "standard": "Variable names should be in snake_case, but 'policy_variables' and 'target_variables' are not explicitly forbidden by the standards, however 'policy_nets' and 'target_nets' should be 'policyNets' and 'targetNets' to follow camelCase for function variables and 'self.policy_scope.name' and 'self.target_scope.name' imply that 'policy_scope' and 'target_scope' should be 'PolicyScope' and 'TargetScope' to follow PascalCase for class names, but without the class definition it is hard to say for sure."
            },
            {
              "location": "line 119",
              "file": "networks/factory.py",
              "standard": "The function 'create_reset_target_network_op' is correctly named in camelCase, but the conditional 'if not (self.policy_nets and self.target_nets)' could be rephrased for better readability, however this does not directly violate any standards."
            },
            {
              "location": "line 127-131",
              "file": "networks/factory.py",
              "standard": "Variable 'from_var' and 'to_var' should be 'fromVar' and 'toVar' to follow camelCase, also 'copy_ops' should be 'copyOps'."
            }
          ]
        },
        {
          "issues": [
            {
              "location": "line 102",
              "file": "networks/inputs.py",
              "standard": "Variable 'placeholder', 'time_offsets', and 'feeds' should be in snake_case"
            },
            {
              "location": "line 103",
              "file": "networks/inputs.py",
              "standard": "Variable 'feeds' should be in snake_case"
            },
            {
              "location": "line 104",
              "file": "networks/inputs.py",
              "standard": "Variable 'placeholder' should be in snake_case"
            }
          ]
        },
        {
          "issues": [
            {
              "location": "line 14",
              "file": "util/util.py",
              "standard": "Variable names should be in snake_case, but 'child' and 'dir' are acceptable. However, 'runs' is also acceptable, but it's worth noting that the function 'find_previous_run' could be improved for readability with snake_case for its variable 'run' in the line below, but more importantly 'find_previous_run' does not follow the standards since it should be in camelCase"
            },
            {
              "location": "line 15",
              "file": "util/util.py",
              "standard": "The function 'find_previous_run' does not follow the standards since it should be in camelCase, it should be 'findPreviousRun'"
            }
          ]
        }
      ],
      "error_analysis": [
        {
          "messages": [
